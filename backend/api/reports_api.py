from fastapi import APIRouter, Depends, HTTPException # Se agrega HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case, extract
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, time, timedelta

from .. import models
from ..database import get_db

router = APIRouter(
    prefix="/api/reports",
    tags=["Reports"]
)

# --- Pydantic Schemas CORREGIDOS ---

class ActivityDetailForReport(BaseModel):
    id: int
    user: Optional[str]
    duration_hours: float
    proyecto_nombre: Optional[str]
    # CAMBIO 1: Agregado el campo is_additional
    is_additional: bool 

class ActivitiesByUser(BaseModel):
    user: str
    ticket_count: int

class SupportHoursDetail(BaseModel):
    client_name: str
    contracted_hours: float
    # El valor consumido aquí puede ser el total, si el frontend filtra
    consumed_hours: float 
    activities: List[ActivityDetailForReport]

class GlobalActivityDetail(BaseModel):
    activity_id: int
    activity_date: datetime
    consultant: Optional[str]
    client_name: Optional[str]
    ticket_id: Optional[int]
    project_name: Optional[str]
    duration_hours: float
    is_additional: bool

# --- Helper Function for Duration Calculation ---

def calculate_duration(hora_inicio: time, hora_fin: time) -> float:
    """Calcula la duración en horas, manejando el cruce de medianoche."""
    if not hora_inicio or not hora_fin:
        return 0.0
    
    start_dt = datetime.combine(datetime.min, hora_inicio)
    end_dt = datetime.combine(datetime.min, hora_fin)
    
    if end_dt < start_dt:
        end_dt += timedelta(days=1)
        
    duration = end_dt - start_dt
    return round(duration.total_seconds() / 3600, 2)

# --- Report Endpoints ---

@router.get("/activities_by_user", response_model=List[ActivitiesByUser])
def get_activities_by_user(db: Session = Depends(get_db)):
    """
    Counts the number of activities assigned to each user with a 'developer' or 'admin' role.
    Filter by the current month.
    """
    # Get users who are developers (3) or admins (1)
    eligible_users = db.query(models.PersonOfCustomer.user).filter(
        models.PersonOfCustomer.roll.in_(['1', '3'])
    ).all()
    
    eligible_user_list = [user[0] for user in eligible_users]

    current_month = datetime.now().month
    current_year = datetime.now().year

    # Count activities grouped by user, only for eligible users and current month
    results = db.query(
        models.Actividad.user,
        func.count(models.Actividad.id)
    ).filter(
        models.Actividad.user.in_(eligible_user_list),
        extract('month', models.Actividad.fecha_creacion) == current_month,
        extract('year', models.Actividad.fecha_creacion) == current_year
    ).group_by(
        models.Actividad.user
    ).all()

    return [{"user": user, "ticket_count": count} for user, count in results]


@router.get("/support_hours/{client_id}", response_model=SupportHoursDetail)
def get_support_hours_by_client_id(client_id: int, db: Session = Depends(get_db)):
    """
    Calculates contracted vs consumed support hours for a specific client
    and returns a detailed list of the activities.
    """
    client = db.query(models.Cliente).filter(models.Cliente.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Consulta las actividades uniendo con Card para obtener AdditionalHoursStatus
    activities_with_card = db.query(models.Actividad, models.Card.AdditionalHoursStatus).options(
        joinedload(models.Actividad.proyecto)
    ).join(
        models.Card, models.Actividad.card_id == models.Card.internalId, isouter=True
    ).filter(
        models.Actividad.cliente_id == client.id
    ).all()
    
    # Dos totales: uno para la suma de todas las horas y otro para las horas de soporte (filtradas)
    total_consumed_support_seconds = 0
    activity_details = []

    for activity, additional_status in activities_with_card:
        
        duration_hours = calculate_duration(activity.hora_inicio, activity.hora_fin)
        duration_seconds = duration_hours * 3600
        
        # Determinar si es adicional. Consideramos adicional si el estado es Aprobado
        is_additional = (additional_status == 'Aprobado')
        
        # Sumar solo las horas que NO son adicionales para el cálculo de soporte
        if not is_additional:
            total_consumed_support_seconds += duration_seconds

        activity_details.append(
            ActivityDetailForReport(
                id=activity.id,
                user=activity.user,
                duration_hours=duration_hours,
                proyecto_nombre=activity.proyecto.nombre if activity.proyecto else "N/A",
                is_additional=is_additional 
            )
        )
    
    consumed_hours = total_consumed_support_seconds / 3600

    return SupportHoursDetail(
        client_name=client.razon_social or client.nombre,
        contracted_hours=client.support_hours or 0.0,
        consumed_hours=round(consumed_hours, 2),
        activities=activity_details
    )


@router.get("/global_activities", response_model=List[GlobalActivityDetail])
def get_global_activities(
    db: Session = Depends(get_db),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    ticket_id: Optional[int] = None,
    is_additional: Optional[bool] = None,
    client_id: Optional[int] = None,
    user_id: Optional[str] = None
):
    """
    Provides a global report of all activities with extensive filtering.
    """
    # Consulta robusta usando etiquetas para la desestructuración
    query = db.query(
        models.Actividad.id.label('activity_id'),
        models.Actividad.fecha_creacion.label('activity_date'),
        models.Actividad.user.label('consultant'),
        models.Cliente.razon_social.label('client_name'),
        models.Actividad.card_id.label('ticket_id'),
        models.Proyecto.nombre.label('project_name'),
        models.Actividad.hora_inicio.label('hora_inicio'),
        models.Actividad.hora_fin.label('hora_fin'),
        models.Card.AdditionalHoursStatus.label('additional_status')
    ).join(models.Cliente, models.Actividad.cliente_id == models.Cliente.id, isouter=True)\
     .join(models.Proyecto, models.Actividad.proyecto_id == models.Proyecto.id, isouter=True)\
     .join(models.Card, models.Actividad.card_id == models.Card.internalId, isouter=True)

    # Apply filters
    if start_date:
        query = query.filter(models.Actividad.fecha_creacion >= start_date.date())
    if end_date:
        query = query.filter(models.Actividad.fecha_creacion <= end_date.date())
    if ticket_id:
        query = query.filter(models.Actividad.card_id == ticket_id)
    if client_id:
        query = query.filter(models.Actividad.cliente_id == client_id)
    if user_id:
        query = query.filter(models.Actividad.user == user_id)
    if is_additional is not None:
        if is_additional:
            query = query.filter(models.Card.AdditionalHoursStatus == 'Aprobado')
        else:
            query = query.filter((models.Card.AdditionalHoursStatus != 'Aprobado') | (models.Card.AdditionalHoursStatus == None))

    results = query.all()

    report_data = []
    
    # Desestructuración para mayor robustez
    for (activity_id, activity_date, consultant, client_name, ticket_id, project_name, 
         hora_inicio, hora_fin, additional_status) in results:
        
        duration_hours = calculate_duration(hora_inicio, hora_fin)

        report_data.append(GlobalActivityDetail(
            activity_id=activity_id,
            activity_date=activity_date,
            consultant=consultant,
            client_name=client_name,
            ticket_id=ticket_id,
            project_name=project_name,
            duration_hours=duration_hours,
            is_additional=(additional_status == 'Aprobado')
        ))

    return report_data