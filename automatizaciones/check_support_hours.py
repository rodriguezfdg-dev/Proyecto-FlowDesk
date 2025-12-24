# -*- coding: utf-8 -*-
"""
Script de Notificación de Consumo de Horas de Soporte

Este script verifica el consumo de horas de soporte de cada cliente y envía
notificaciones cuando se alcanzan los umbrales del 80%, 100% y 120%.

Ejecución: python check_support_hours.py
Recomendado: Programar como tarea diaria a las 8:00 AM
"""
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone, timedelta

# --- DATABASE SETUP ---
try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env.local')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
except ImportError:
    print("python-dotenv not found, relying on system environment variables.")
    pass

from backend import models
from backend.core.email import send_email

DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "root")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_NAME = os.getenv("DB_NAME", "innovaweb")

DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def calculate_duration(hora_inicio, hora_fin):
    """Calcula la duración en horas, manejando el cruce de medianoche."""
    if not hora_inicio or not hora_fin:
        return 0.0
    
    from datetime import datetime, timedelta
    start_dt = datetime.combine(datetime.min, hora_inicio)
    end_dt = datetime.combine(datetime.min, hora_fin)
    
    if end_dt < start_dt:
        end_dt += timedelta(days=1)
        
    duration = end_dt - start_dt
    return round(duration.total_seconds() / 3600, 2)


def get_admin_emails(db):
    """Obtiene los emails de todos los administradores (rol 1)."""
    admins = db.query(models.PersonOfCustomer).filter(
        models.PersonOfCustomer.roll == '1',
        models.PersonOfCustomer.gmail.isnot(None)
    ).all()
    return [admin.gmail for admin in admins if admin.gmail]


def get_client_encargados_emails(db, cliente):
    """Obtiene los emails de los encargados del cliente."""
    emails = []
    if cliente.encargados:
        # Los encargados están separados por comas
        encargado_names = [e.strip() for e in cliente.encargados.split(',')]
        for name in encargado_names:
            person = db.query(models.PersonOfCustomer).filter(
                models.PersonOfCustomer.user == name,
                models.PersonOfCustomer.gmail.isnot(None)
            ).first()
            if person and person.gmail:
                emails.append(person.gmail)
    return emails


def send_threshold_notification(db, cliente, percentage, consumed_hours, remaining_hours, admin_emails):
    """Envía notificación según el umbral alcanzado."""
    
    client_name = cliente.razon_social or cliente.nombre or cliente.code
    
    # Determinar tipo de notificación
    if percentage >= 120:
        level = 120
        subject = f"⚠️ {client_name}: Has excedido tus horas de soporte en un {int(percentage - 100)}%"
        color = "#dc2626"  # Red
        icon = "🔴"
        message = f"""
        <p>Has <strong>excedido</strong> tus horas contratadas.</p>
        <p>Las horas adicionales consumidas se facturarán por separado.</p>
        """
    elif percentage >= 100:
        level = 100
        subject = f"🔴 {client_name}: Has agotado tus horas de soporte"
        color = "#dc2626"  # Red
        icon = "🔴"
        message = f"""
        <p>Has consumido <strong>todas</strong> tus horas contratadas.</p>
        <p>Nuevas actividades se facturarán como horas adicionales.</p>
        <p>Contacta a tu ejecutivo para renovar tu plan.</p>
        """
    else:  # 80%
        level = 80
        subject = f"⚠️ {client_name}: Has consumido el {int(percentage)}% de tus horas de soporte"
        color = "#f59e0b"  # Amber
        icon = "⚠️"
        message = f"""
        <p>Te estás acercando al límite de tus horas contratadas.</p>
        <p>Considera contratar horas adicionales para evitar interrupciones.</p>
        """
    
    # Plantilla HTML
    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f3f4f6; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, {color} 0%, {color}dd 100%); color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ padding: 30px; }}
            .stats {{ background-color: #f9fafb; border-radius: 8px; padding: 20px; margin: 20px 0; }}
            .stat-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e5e7eb; }}
            .stat-row:last-child {{ border-bottom: none; }}
            .stat-label {{ color: #6b7280; font-weight: 500; }}
            .stat-value {{ color: #111827; font-weight: 700; }}
            .footer {{ background-color: #f9fafb; padding: 20px; text-align: center; color: #6b7280; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{icon} Alerta de Consumo de Horas</h1>
            </div>
            <div class="content">
                <h2>Hola, {client_name}</h2>
                {message}
                
                <div class="stats">
                    <div class="stat-row">
                        <span class="stat-label">Horas Contratadas:</span>
                        <span class="stat-value">{cliente.support_hours:.2f} hrs</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Horas Consumidas:</span>
                        <span class="stat-value">{consumed_hours:.2f} hrs</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Horas Restantes:</span>
                        <span class="stat-value" style="color: {color};">{remaining_hours:.2f} hrs</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Porcentaje Consumido:</span>
                        <span class="stat-value" style="color: {color};">{percentage:.1f}%</span>
                    </div>
                </div>
                
                <p style="margin-top: 20px;">
                    Para más detalles, ingresa al sistema o contacta a tu ejecutivo de cuenta.
                </p>
            </div>
            <div class="footer">
                <p>Este es un mensaje automático del sistema de gestión de tickets.</p>
                <p>© {datetime.now().year} Flowdesk - Innova ERP</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Enviar a cliente
    recipients = []
    if cliente.email:
        recipients.append(cliente.email)
    
    # Agregar encargados
    encargados_emails = get_client_encargados_emails(db, cliente)
    recipients.extend(encargados_emails)
    
    # Enviar emails
    sent_count = 0
    for recipient in recipients:
        try:
            send_email(recipient, subject, body)
            print(f"  ✓ Notificación enviada a {recipient}")
            sent_count += 1
        except Exception as e:
            print(f"  ✗ Error enviando a {recipient}: {e}")
    
    # Notificar a administradores
    admin_subject = f"[ADMIN] {subject}"
    for admin_email in admin_emails:
        try:
            send_email(admin_email, admin_subject, body)
            print(f"  ✓ Notificación enviada a admin {admin_email}")
            sent_count += 1
        except Exception as e:
            print(f"  ✗ Error enviando a admin {admin_email}: {e}")
    
    return sent_count, level


def check_support_hours():
    """
    Función principal que verifica el consumo de horas de todos los clientes
    y envía notificaciones según los umbrales configurados.
    """
    db = SessionLocal()
    print(f"--- Verificación de Horas de Soporte: {datetime.now(timezone.utc)} ---")
    print(f"Conectando a DB: {DB_HOST}:{DB_PORT} como {DB_USER}")
    
    try:
        # Obtener emails de administradores
        admin_emails = get_admin_emails(db)
        print(f"Administradores a notificar: {len(admin_emails)}")
        
        # Obtener todos los clientes activos con horas contratadas
        clientes = db.query(models.Cliente).filter(
            models.Cliente.support_hours > 0,
            models.Cliente.estado != 'Closed'
        ).all()
        
        print(f"Clientes activos con horas contratadas: {len(clientes)}\n")
        
        notifications_sent = 0
        clients_notified = 0
        
        for cliente in clientes:
            # Calcular horas consumidas desde actividades (excluyendo adicionales)
            activities = db.query(models.Actividad, models.Card.AdditionalHoursStatus).join(
                models.Card, models.Actividad.card_id == models.Card.internalId, isouter=True
            ).filter(
                models.Actividad.cliente_id == cliente.id
            ).all()
            
            consumed_hours = 0.0
            for activity, additional_status in activities:
                # Solo contar si NO es adicional aprobado
                if additional_status != 'Aprobado':
                    duration = calculate_duration(activity.hora_inicio, activity.hora_fin)
                    consumed_hours += duration
            
            # Calcular porcentaje
            if cliente.support_hours > 0:
                percentage = (consumed_hours / cliente.support_hours) * 100
            else:
                continue
            
            # Determinar umbral alcanzado
            threshold_reached = None
            if percentage >= 120:
                threshold_reached = 120
            elif percentage >= 100:
                threshold_reached = 100
            elif percentage >= 80:
                threshold_reached = 80
            
            # Verificar si ya se notificó este umbral
            if threshold_reached and threshold_reached > cliente.last_alert_level:
                client_name = cliente.razon_social or cliente.nombre or cliente.code
                remaining_hours = max(0, cliente.support_hours - consumed_hours)
                
                print(f"Cliente: {client_name}")
                print(f"  Horas: {consumed_hours:.2f}/{cliente.support_hours:.2f} ({percentage:.1f}%)")
                print(f"  Umbral alcanzado: {threshold_reached}% (anterior: {cliente.last_alert_level}%)")
                
                sent, level = send_threshold_notification(
                    db, cliente, percentage, consumed_hours, remaining_hours, admin_emails
                )
                
                if sent > 0:
                    # Actualizar último nivel de alerta
                    cliente.last_alert_level = level
                    notifications_sent += sent
                    clients_notified += 1
                    print(f"  ✓ {sent} notificaciones enviadas\n")
                else:
                    print(f"  ✗ No se pudieron enviar notificaciones\n")
        
        # Commit de cambios
        db.commit()
        
        print(f"\n--- Resumen ---")
        print(f"Clientes notificados: {clients_notified}")
        print(f"Notificaciones enviadas: {notifications_sent}")
        
    except Exception as e:
        print(f"Error inesperado: {e}")
        db.rollback()
    finally:
        print("--- Verificación finalizada ---")
        db.close()


if __name__ == "__main__":
    check_support_hours()
