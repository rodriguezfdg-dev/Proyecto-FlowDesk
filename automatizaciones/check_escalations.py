# -*- coding: utf-8 -*-
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone

# --- DATABASE SETUP (Correct Way) ---
# Replicating the connection method from backend/database.py
# This ensures the script uses the same environment variables as the main app.
try:
    from dotenv import load_dotenv
    # Assuming the script is run from the root directory where .env.local is
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env.local')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
    else:
        # Fallback for environments where .env isn't used (like production servers)
        pass 
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

def get_customer_email(db, customer_code):
    """Fetches the email for a given customer code."""
    # It's possible the customer was deleted, handle this gracefully.
    customer = db.query(models.Cliente).filter(models.Cliente.code == customer_code).first()
    if customer:
        # Assuming the customer's email is in the 'email' field
        # Need to query PersonOfCustomer for the actual user who created it
        main_contact_email = customer.email
        # This part is tricky, the ticket doesn't store who created it, just the client.
        # We will assume notifying the main client contact is correct.
        return main_contact_email
    return None

def check_ticket_escalations():
    """
    Main function to check all open tickets and send escalation notifications
    based on the configured attention flow rules.
    """
    db = SessionLocal()
    print(f"--- Running escalation check at {datetime.now(timezone.utc)} ---")
    print(f"Connecting to DB: {DB_HOST}:{DB_PORT} as {DB_USER}")

    try:
        # 1. Fetch Attention Flow Settings
        settings = db.query(models.AttentionFlowSettings).first()
        if not settings:
            print("AttentionFlowSettings not found. Aborting.")
            return

        print(f"Loaded settings: Nuevo={settings.max_time_new}h, Pendiente={settings.max_time_pending}h, Pruebas={settings.max_time_testing}h, Espera={settings.max_time_waiting}h")
        print(f"Priority settings: Low={settings.max_time_priority_low}h, Medium={settings.max_time_priority_medium}h, High={settings.max_time_priority_high}h, Critical={settings.max_time_priority_critical}h")

        # 2. Fetch all open tickets that have a state change date
        open_tickets = db.query(models.Card).filter(
            models.Card.State.notin_(['Cerrado', 'Terminado']),
            models.Card.state_last_changed_date.isnot(None)
        ).all()
        
        print(f"Found {len(open_tickets)} open tickets to check.")

        now = datetime.now(timezone.utc)

        # 3. Iterate through tickets and apply rules
        for ticket in open_tickets:
            # Ensure state_last_changed_date is aware (assuming UTC if naive)
            last_changed = ticket.state_last_changed_date
            if last_changed and last_changed.tzinfo is None:
                last_changed = last_changed.replace(tzinfo=timezone.utc)
            
            time_in_state = now - last_changed
            
            # Rule for "En espera de respuesta" -> Notify Customer every 48h
            if ticket.State == 'En espera de respuesta':
                max_hours = settings.max_time_waiting
                reminder_interval_hours = 48
                
                if max_hours > 0 and time_in_state > timedelta(hours=max_hours):
                    # Ensure last_escalation_sent_date is aware if it exists
                    last_escalation = ticket.last_escalation_sent_date
                    if last_escalation and last_escalation.tzinfo is None:
                        last_escalation = last_escalation.replace(tzinfo=timezone.utc)

                    should_notify = not last_escalation or \
                                    (now - last_escalation) >= timedelta(hours=reminder_interval_hours)
                    
                    if should_notify:
                        print(f"Ticket #{ticket.internalId} ('En espera de respuesta') has exceeded {max_hours}h. Notifying customer.")
                        # This logic needs to identify the CREATOR of the ticket, not the client contact.
                        # The Card model does not store the creator. This is a limitation.
                        # We will notify the main client contact as a fallback.
                        customer_email = get_customer_email(db, ticket.CustCode)
                        if customer_email:
                            subject = f"Recordatorio: Ticket #{ticket.internalId} en espera de su respuesta"
                            body = f"<p>Hola,</p><p>Te recordamos que el ticket '{ticket.Name}' sigue esperando una respuesta de tu parte para poder continuar.</p><p>Por favor, revisa el ticket en el sistema.</p>"
                            try:
                                send_email(customer_email, subject, body)
                                ticket.last_escalation_sent_date = now
                                print(f"  > Notification sent to customer at {customer_email}")
                            except Exception as e:
                                print(f"  > FAILED to send email to {customer_email}: {e}")
                        else:
                            print(f"  > Could not find customer email for ticket #{ticket.internalId}")

            # General Rule for other states -> Notify Assignee
            else:
                reminder_interval_hours = 24
                max_hours = 0
                
                # Determine max_hours based on Priority first
                priority_max_hours = 0
                if ticket.Priority == 'Baja':
                    priority_max_hours = settings.max_time_priority_low
                elif ticket.Priority == 'Media':
                    priority_max_hours = settings.max_time_priority_medium
                elif ticket.Priority == 'Alta':
                    priority_max_hours = settings.max_time_priority_high
                elif ticket.Priority == 'Crítica' or ticket.Priority == 'Critica':
                    priority_max_hours = settings.max_time_priority_critical
                
                if priority_max_hours > 0:
                    max_hours = priority_max_hours
                    # print(f"  > Ticket #{ticket.internalId}: Using Priority '{ticket.Priority}' limit: {max_hours}h")
                else:
                    # Fallback to State-based limits
                    if ticket.State == 'Nuevo' and settings.max_time_new > 0:
                        max_hours = settings.max_time_new
                    elif ticket.State == 'Pendiente' and settings.max_time_pending > 0:
                        max_hours = settings.max_time_pending
                    elif ticket.State == 'En pruebas' and settings.max_time_testing > 0:
                        max_hours = settings.max_time_testing
                
                if max_hours > 0 and time_in_state > timedelta(hours=max_hours):
                    # Ensure last_escalation_sent_date is aware if it exists
                    last_escalation = ticket.last_escalation_sent_date
                    if last_escalation and last_escalation.tzinfo is None:
                        last_escalation = last_escalation.replace(tzinfo=timezone.utc)

                    should_notify = not last_escalation or \
                                    (now - last_escalation) >= timedelta(hours=reminder_interval_hours)
                            
                    if should_notify and ticket.assign:
                        print(f"Ticket #{ticket.internalId} ('{ticket.State}', Priority: {ticket.Priority}) has exceeded {max_hours}h. Notifying assignee '{ticket.assign}'.")
                        assignee = db.query(models.PersonOfCustomer).filter(models.PersonOfCustomer.user == ticket.assign).first()
                        if assignee and assignee.gmail:
                            subject = f"Alerta: Ticket #{ticket.internalId} ha excedido el tiempo límite"
                            body = f"<p>Hola {ticket.assign},</p><p>Te informamos que el ticket '{ticket.Name}' (Prioridad: {ticket.Priority}) ha permanecido en estado '{ticket.State}' por más tiempo del configurado ({max_hours} horas).</p><p>Por favor, revisa el ticket en el sistema.</p>"
                            try:
                                send_email(assignee.gmail, subject, body)
                                ticket.last_escalation_sent_date = now
                                print(f"  > Notification sent to assignee at {assignee.gmail}")
                            except Exception as e:
                                print(f"  > FAILED to send email to {assignee.gmail}: {e}")
                        else:
                            print(f"  > Could not find assignee email for user '{ticket.assign}'")

        db.commit()

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        db.rollback()
    finally:
        print("--- Escalation check finished ---")
        db.close()

if __name__ == "__main__":
    check_ticket_escalations()