from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from .. import models
from ..database import get_db
from ..core.email import send_email # Import send_email
from .users_api import get_current_user

router = APIRouter(
    prefix="/api",
    tags=["Actividades"]
)

# Pydantic Models (Schemas)
class ActivityCreate(BaseModel):
    titulo: str
    descripcion: str
    hora_inicio: datetime
    hora_fin: datetime
    cliente_id: int
    # Classification fields (using existing DB columns)
    type_user: Optional[str] = None  # Task type: Programación, Consultoría, Reunión, Presencial
    activity_subtype: Optional[str] = None  # Subtype
    overtime: Optional[float] = None  # Hours to compensate
    proyecto_id: Optional[int] = None
    card_id: Optional[int] = None
    update_ticket_additional_status: Optional[bool] = False

class ActivityResponse(BaseModel):
    id: int
    titulo: str
    descripcion: str
    hora_inicio: datetime
    hora_fin: datetime
    cliente_id: int
    user: Optional[str] = None
    # Classification fields (using existing DB columns)
    type_user: Optional[str] = None
    activity_subtype: Optional[str] = None
    overtime: Optional[float] = None
    proyecto_id: Optional[int] = None
    card_id: Optional[int] = None

    class Config:
        from_attributes = True

class ActivityDetailResponse(ActivityResponse):
    proyecto_nombre: Optional[str] = None

# Endpoints for Actividades

@router.post("/actividades/", response_model=ActivityResponse, tags=["Actividades"])
def create_actividad(actividad: ActivityCreate, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    
    # 1. Find the client
    cliente = db.query(models.Cliente).filter(models.Cliente.id == actividad.cliente_id).first()
    
    # Fallback: Try finding by Code (as string) if not found by ID
    if not cliente:
        cliente = db.query(models.Cliente).filter(models.Cliente.code == str(actividad.cliente_id)).first()

    if not cliente:
        raise HTTPException(status_code=404, detail=f"Cliente with ID {actividad.cliente_id} not found")

    # 1.5 Check for overlapping activities for the same user
    # Get all activities for the current user on the same day
    same_day_activities = db.query(models.Actividad).filter(
        models.Actividad.user == current_user.user,
        models.Actividad.fecha_creacion == actividad.hora_inicio.date()
    ).all()

    new_start = actividad.hora_inicio.time()
    new_end = actividad.hora_fin.time()

    for existing_act in same_day_activities:
        # Check for overlap: (StartA < EndB) and (EndA > StartB)
        if new_start < existing_act.hora_fin and new_end > existing_act.hora_inicio:
            raise HTTPException(status_code=400, detail="Superposición de horarios con otras actividades existentes")

    # 2. Calculate duration in hours
    duration_timedelta = actividad.hora_fin - actividad.hora_inicio
    duration_hours = duration_timedelta.total_seconds() / 3600.0
    
    if duration_hours <= 0:
        raise HTTPException(status_code=400, detail="End time must be after start time.")

    # 3. Update client's consumed hours
    cliente.support_hours_consumed += duration_hours

    print(f"DEBUG: Cliente ID: {cliente.id}, Horas de soporte: {cliente.support_hours}, Horas consumidas: {cliente.support_hours_consumed}")
    print(f"DEBUG: Last Alert Level: {cliente.last_alert_level}")

    # 4. Check for support hour thresholds and send alerts
    if cliente.support_hours > 0: # Avoid division by zero
        utilization_percentage = (cliente.support_hours_consumed / cliente.support_hours) * 100
        print(f"DEBUG: Porcentaje de utilización: {utilization_percentage}")
        alert_thresholds = [80.0, 100.0, 120.0] # Define thresholds

        for threshold in sorted(alert_thresholds):
            print(f"DEBUG: Checking threshold {threshold}. Current utilization: {utilization_percentage}. Last alert level: {cliente.last_alert_level}")
            if utilization_percentage >= threshold and cliente.last_alert_level < threshold:
                print(f"DEBUG: Threshold {threshold} met and alert not sent yet. Searching for support managers.")
                # Find support managers belonging to the client to send email to
                support_managers = db.query(models.PersonOfCustomer).filter(
                    models.PersonOfCustomer.roll == 4, # Changed from string to integer 4
                    models.PersonOfCustomer.cliente_id == cliente.id
                ).all() # Assuming "gerente de soporte" is the role and client_id links managers to clients

                print(f"DEBUG: Found {len(support_managers)} support managers.")
                if support_managers:
                    subject = f"Alerta de Bolsa de Horas - Cliente {cliente.nombre} al {int(threshold)}%"
                    body = f"""
Estimado Gerente de Soporte,

Este es un aviso automático de que la bolsa de horas del cliente "{cliente.nombre}" (ID: {cliente.id}) ha alcanzado o superado el {int(threshold)}% de utilización.

Detalles actuales:
- Horas Totales Asignadas: {cliente.support_hours:.2f}
- Horas Consumidas: {cliente.support_hours_consumed:.2f}
- Porcentaje de Utilización: {utilization_percentage:.2f}%

Por favor, tome las acciones necesarias.

Saludos,
Sistema de Tickets Innova
                    """
                    for manager in support_managers:
                        print(f"DEBUG: Manager found - ID: {manager.id}, Gmail: {manager.gmail}")
                        if manager.gmail:
                            try:
                                send_email(manager.gmail, subject, body)
                                print(f"DEBUG: Email de alerta enviado a {manager.gmail} para cliente {cliente.nombre} al {int(threshold)}%")
                            except Exception as e:
                                print(f"ERROR: Fallo al enviar email de alerta a {manager.gmail}: {e}")
                        else:
                            print(f"DEBUG: Gerente de soporte {manager.id} no tiene un email configurado.")
                else:
                    print("DEBUG: No support managers found with roll 4 for this client.")
                
                # Update last_alert_level to prevent sending the same alert multiple times
                cliente.last_alert_level = threshold
                # No need to break, as multiple thresholds might be crossed at once (e.g., from 70% to 110%)
                # The loop handles ensuring alerts are sent only for new thresholds.

    # Map task_type string to integer
    task_type_mapping = {
        "Programación": 1,
        "Consultoría": 2,
        "Reunión": 3,
        "Presencial": 4
    }
    # Use type_user from the request (which contains the string)
    task_type_int = task_type_mapping.get(actividad.type_user) if actividad.type_user else None

    # Calculate overtime if checked
    overtime_value = actividad.overtime
    if actividad.overtime and actividad.overtime > 0:
         # duration_hours is already calculated above
         overtime_value = duration_hours

    # 5. Create the activity record
    db_actividad = models.Actividad(
        titulo=actividad.titulo,
        descripcion=actividad.descripcion,
        hora_inicio=actividad.hora_inicio.time(),
        hora_fin=actividad.hora_fin.time(),
        fecha_creacion=actividad.hora_inicio.date(),
        cliente_id=cliente.id,
        user=current_user.user,
        prioridad=2, 
        tipo="SOPORTE",
        estado=2,
        # Classification fields (using existing DB columns)
        type_user=task_type_int,
        activity_subtype=actividad.activity_subtype,
        overtime=overtime_value,
        proyecto_id=actividad.proyecto_id,
        card_id=actividad.card_id
    )

    db.add(db_actividad)
    db.add(cliente) 
    db.commit()
    db.refresh(db_actividad)

    # 6. Update Ticket Status if requested
    if actividad.update_ticket_additional_status and actividad.card_id:
        card = db.query(models.Card).filter(models.Card.internalId == actividad.card_id).first()
        if card:
            # Only update if not already set to avoid overwriting existing status
            if not card.AdditionalHoursStatus or card.AdditionalHoursStatus == 'No Adicional':
                card.AdditionalHoursStatus = 'Pendiente de Aprobacion'
                db.commit()
                print(f"DEBUG: Updated Ticket {card.internalId} AdditionalHoursStatus to 'Pendiente de Aprobacion'")
    
    # Reverse mapping for response
    task_type_mapping_rev = {
        1: "Programación",
        2: "Consultoría",
        3: "Reunión",
        4: "Presencial"
    }
    task_type_str = task_type_mapping_rev.get(db_actividad.type_user) if db_actividad.type_user else None

    # Manually construct the response
    return ActivityResponse(
        id=db_actividad.id,
        titulo=db_actividad.titulo,
        descripcion=db_actividad.descripcion,
        hora_inicio=datetime.combine(db_actividad.fecha_creacion, db_actividad.hora_inicio),
        hora_fin=datetime.combine(db_actividad.fecha_creacion, db_actividad.hora_fin),
        cliente_id=db_actividad.cliente_id,
        user=db_actividad.user,
        type_user=task_type_str, # Changed from task_type to type_user to match schema
        activity_subtype=db_actividad.activity_subtype, # Added missing field
        overtime=db_actividad.overtime, # Added missing field
        proyecto_id=db_actividad.proyecto_id,
        card_id=db_actividad.card_id
    )

@router.get("/actividades/{actividad_id}", response_model=ActivityDetailResponse, tags=["Actividades"])
def read_actividad(actividad_id: int, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    # Use joinedload to fetch the related project in the same query
    db_actividad = db.query(models.Actividad).options(joinedload(models.Actividad.proyecto)).filter(models.Actividad.id == actividad_id).first()

    if db_actividad is None:
        raise HTTPException(status_code=404, detail="Actividad not found")

    # --- CORRECCIÓN DE SEGURIDAD ---
    # Permitir ver si: Es el dueño de la actividad O si es Admin/Soporte (Roles '1' o '3')
    is_owner = db_actividad.user.lower() == current_user.user.lower()
    is_admin_or_manager = current_user.roll in ['1', '3'] # Ajusta los roles según tu lógica de Innova
    
    if not is_owner and not is_admin_or_manager:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver esta actividad")
    # -------------------------------

    # Handle cases where hora_inicio or fecha_creacion might be None
    start_datetime = datetime.combine(db_actividad.fecha_creacion, db_actividad.hora_inicio) if db_actividad.fecha_creacion and db_actividad.hora_inicio else None
    end_datetime = datetime.combine(db_actividad.fecha_creacion, db_actividad.hora_fin) if db_actividad.fecha_creacion and db_actividad.hora_fin else None
    
    if not start_datetime or not end_datetime:
         # En lugar de error 500, devolvemos nulos o manejamos el error suavemente si es necesario
         pass 

    return ActivityDetailResponse(
        id=db_actividad.id,
        titulo=db_actividad.titulo,
        descripcion=db_actividad.descripcion,
        hora_inicio=start_datetime,
        hora_fin=end_datetime,
        cliente_id=db_actividad.cliente_id,
        user=db_actividad.user,
        # Classification fields mapping
        type_user=None, # Puedes mapear esto si lo necesitas en el detalle
        activity_subtype=db_actividad.activity_subtype,
        overtime=db_actividad.overtime,
        proyecto_id=db_actividad.proyecto_id,
        card_id=db_actividad.card_id,
        proyecto_nombre=db_actividad.proyecto.nombre if db_actividad.proyecto else "N/A"
    )

@router.get("/actividades/", response_model=List[ActivityResponse], tags=["Actividades"])

def read_actividades(

    skip: int = 0, 

    limit: int = 100, 

    db: Session = Depends(get_db), 

    current_user: models.PersonOfCustomer = Depends(get_current_user),

    cliente_id: Optional[int] = None,

    start_date: Optional[datetime] = None,

    end_date: Optional[datetime] = None

):

    # Start with a query filtered by the current user

    query = db.query(models.Actividad).filter(models.Actividad.user == current_user.user)



    # Apply optional filters

    if cliente_id:

        query = query.filter(models.Actividad.cliente_id == cliente_id)

    if start_date:

        query = query.filter(models.Actividad.fecha_creacion >= start_date.date())

    if end_date:

        # Add one day to the end date to make the range inclusive

        query = query.filter(models.Actividad.fecha_creacion <= end_date.date())



    actividades = query.offset(skip).limit(limit).all()

    

    response = []

    for act in actividades:

        # Handle cases where hora_inicio or fecha_creacion might be None

        start_datetime = datetime.combine(act.fecha_creacion, act.hora_inicio) if act.fecha_creacion and act.hora_inicio else None

        end_datetime = datetime.combine(act.fecha_creacion, act.hora_fin) if act.fecha_creacion and act.hora_fin else None



        if start_datetime and end_datetime:

            response.append(ActivityResponse(

                id=act.id,

                titulo=act.titulo,

                descripcion=act.descripcion,

                hora_inicio=start_datetime,

                hora_fin=end_datetime,

                cliente_id=act.cliente_id,

                user=act.user

            ))

    return response

@router.get("/reports/additional-hours/{cliente_id}", tags=["Reportes"])
def get_additional_hours_report(cliente_id: int, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    # 1. Get all tickets (Cards) for the client that have AdditionalHoursStatus set (assuming not null means relevant)
    # Adjust the filter based on exact requirements. Here assuming "Pendiente de Aprobacion" or others are relevant.
    # Or maybe we want ALL tickets that have activities with overtime?
    # The requirement says: "Additional Hours is when the client requests a quote... and approves additional hours".
    # So we look for tickets where AdditionalHoursStatus is not null/empty.
    
    tickets = db.query(models.Card).filter(
        models.Card.CustCode == db.query(models.Cliente.code).filter(models.Cliente.id == cliente_id).scalar_subquery(),
        models.Card.AdditionalHoursStatus != None,
        models.Card.AdditionalHoursStatus != ""
    ).all()

    report_data = []
    total_approved = 0.0
    total_consumed = 0.0

    for ticket in tickets:
        # Approved Hours
        approved_hours = ticket.HourCot if ticket.HourCot else 0.0
        
        # Consumed Hours: Sum of duration of linked activities
        # We need to calculate duration for each activity linked to this card
        consumed_hours = 0.0
        
        # Fetch activities linked to this card
        activities = db.query(models.Actividad).filter(models.Actividad.card_id == ticket.internalId).all()
        
        for act in activities:
            if act.hora_inicio and act.hora_fin:
                # Calculate duration
                start = datetime.combine(datetime.min, act.hora_inicio)
                end = datetime.combine(datetime.min, act.hora_fin)
                duration = (end - start).total_seconds() / 3600.0
                if duration > 0:
                    consumed_hours += duration

        balance = approved_hours - consumed_hours
        
        total_approved += approved_hours
        total_consumed += consumed_hours

        report_data.append({
            "ticket_id": ticket.internalId,
            "ticket_title": ticket.Name,
            "approved_hours": approved_hours,
            "consumed_hours": consumed_hours,
            "balance": balance,
            "status": ticket.AdditionalHoursStatus
        })

    return {
        "details": report_data,
        "summary": {
            "total_approved": total_approved,
            "total_consumed": total_consumed,
            "total_balance": total_approved - total_consumed
        }
    }

