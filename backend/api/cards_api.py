from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime, timezone

from .. import models
from ..database import get_db
from .users_api import get_current_user
from ..core.email import send_email
from ..models import PersonOfCustomer

router = APIRouter(
    prefix="/api",
    tags=["Cards"]
)

TRANSITION_RULES = {
    "Nuevo": ["Pendiente"],
    "Pendiente": ["En proceso", "En pruebas", "Cerrado"],
    "En proceso": ["Pendiente", "En pruebas", "Cerrado", "Esperando respuesta"],
    "En pruebas": ["Cerrado", "En proceso", "Pendiente", "Esperando respuesta"],
    "Cerrado": ["Pendiente", "En proceso", "En pruebas", "Esperando respuesta"],
    "Esperando respuesta": ["En proceso", "En pruebas", "Cerrado", "Pendiente"],
}

class CardBase(BaseModel):
    Name: Optional[str] = None
    CustName: Optional[str] = None
    Comment: Optional[str] = None
    Priority: Optional[str] = None
    State: Optional[str] = None
    CustCode: Optional[str] = None
    assign: Optional[str] = None
    AdditionalHoursStatus: Optional[str] = None
    LinkTrello: Optional[str] = None
    # ELIMINADO: TrelloId: Optional[str] = None
    ModuleID: Optional[int] = None # NUEVO CAMPO: ID interno del módulo
    HourCot: Optional[float] = None
class CardCreate(CardBase):
    Date: date

class CardResponse(CardBase):
    internalId: int
    
    class Config:
        from_attributes = True

class CardDetailResponse(CardResponse):
    customer_internal_id: Optional[int] = None

class CardAssignRequest(BaseModel):
    assign: Optional[str] = None

def _send_assignment_notification(db: Session, db_card: models.Card, new_assignee: str):
    if not new_assignee:
        return
    assigned_user = db.query(PersonOfCustomer).filter(PersonOfCustomer.user == new_assignee).first()
    if assigned_user and assigned_user.gmail:
        client_name = db_card.CustName or "Cliente Desconocido"
        if db_card.cliente:
             client_name = db_card.cliente.razon_social
        
        subject = f"Ticket Asignado: #{db_card.internalId} - {client_name} - {db_card.Name}"
        body = f"<html><body><p>Hola {new_assignee},</p><p>Se te ha asignado un nuevo ticket:</p><p><strong>ID:</strong> #{db_card.internalId}<br><strong>Cliente:</strong> {client_name}<br><strong>Título:</strong> {db_card.Name}</p></body></html>"
        try:
            send_email(assigned_user.gmail, subject, body)
            print(f"Notification email sent to {assigned_user.gmail} for ticket {db_card.internalId}")
        except Exception as e:
            print(f"Failed to send email for ticket {db_card.internalId}: {e}")
    else:
        print(f"Could not send notification: User {new_assignee} not found or has no email.")

@router.put("/cards/{card_id}/assign", response_model=CardResponse, tags=["Cards"])
def update_card_assign(
    card_id: int, 
    assign_request: CardAssignRequest, 
    db: Session = Depends(get_db), 
    current_user: models.PersonOfCustomer = Depends(get_current_user)
):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Not authorized")

    db_card = db.query(models.Card).filter(models.Card.internalId == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card not found")

    old_assignee = db_card.assign
    new_assignee = assign_request.assign
    
    db_card.assign = new_assignee
    db.commit()
    db.refresh(db_card)

    if new_assignee and new_assignee != old_assignee:
        _send_assignment_notification(db, db_card, new_assignee)

    return db_card

@router.post("/cards/", response_model=CardResponse, tags=["Cards"])
def create_card(card: CardCreate, db: Session = Depends(get_db)):
    db_card_data = card.dict(exclude_unset=True)
    
    if 'Date' in db_card_data:
        db_card_data['date_column'] = db_card_data.pop('Date')
    
    # --------------------------------------------------------
    # NUEVA LÓGICA DE ASIGNACIÓN AUTOMÁTICA POR MODULE ID
    # --------------------------------------------------------
    assigned_from_module = False
    module_id = db_card_data.pop('ModuleID', None) # Extraer y usar el nuevo campo

    # 1. Intentar asignar basado en el ModuleID (Prioridad Alta)
    if module_id:
        # models.Board es tu tabla de Módulos (antes Trello Boards)
        # Aquí filtramos por el ID interno del módulo (module_id)
        board = db.query(models.Board).filter(models.Board.internalId == module_id).first() 
        
        if board and board.Department:
            # Buscar el Encargado del Departamento
            dept_manager_row = db.query(models.DepartmentManagerRow).filter(
                models.DepartmentManagerRow.department == board.Department
            ).first()
            
            if dept_manager_row:
                # Obtener el nombre de usuario del encargado
                manager_user = db.query(models.PersonOfCustomer).filter(
                    models.PersonOfCustomer.id == dept_manager_row.in_charge_id
                ).first()
                
                if manager_user:
                    db_card_data['assign'] = manager_user.user
                    assigned_from_module = True
                    print(f"DEBUG: Auto-assigned ticket to {manager_user.user} via Module {board.Name} (Dept: {board.Department})")
    
    # Si la asignación se hizo mediante el ModuleID, no continuamos
    # --------------------------------------------------------
    
    # 2. Lógica de asignación de respaldo (Fallback) si NO fue asignado por módulo
    if not assigned_from_module and db_card_data.get('CustCode'):
        customer = db.query(models.Cliente).filter(models.Cliente.code == db_card_data['CustCode']).first()
        if customer:
            db_card_data['CustName'] = customer.razon_social
            # Asignar al primer encargado por defecto (Lógica de respaldo original)
            if customer.encargados:
                first_encargado = customer.encargados.split(',')[0].strip()
                if first_encargado:
                    db_card_data['assign'] = first_encargado

    db_card_data['state_last_changed_date'] = datetime.now(timezone.utc)
    db_card_data['last_escalation_sent_date'] = None

    db_card = models.Card(**db_card_data)
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
    
    # Send Notification
    if db_card.assign:
        _send_assignment_notification(db, db_card, db_card.assign)
    elif db_card.CustCode and not assigned_from_module:
        # Fallback notification logic (notify all customer encargados if no specific assignee)
        customer = db.query(models.Cliente).filter(models.Cliente.code == db_card.CustCode).first()
        if customer and customer.encargados:
            all_encargados = [name.strip() for name in customer.encargados.split(',') if name.strip()]
            for encargado_name in all_encargados:
                # Avoid double sending if we already assigned to the first one
                if encargado_name != db_card.assign: 
                    _send_assignment_notification(db, db_card, encargado_name)
        
    return db_card

@router.get("/cards/", response_model=List[CardResponse], tags=["Cards"])
def read_cards(
    skip: int = 0, 
    limit: int = 100, 
    search_term: Optional[str] = None,
    Status: Optional[str] = None,
    Priority: Optional[str] = None,
    CustCode: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: models.PersonOfCustomer = Depends(get_current_user)
):
    query = db.query(models.Card)
    
    # Filter by client if the user is a client (Role 2 or 4, or has cliente_id)
    # Assuming role '2' is Cliente and '4' is also related to client (Gerente Soporte)
    # Safer to check if they have a cliente_id and are NOT admin/support staff (Role 1 or 3)
    if current_user.roll not in ['1', '3'] and current_user.cliente_id:
        # Fetch client code
        client = db.query(models.Cliente).filter(models.Cliente.id == current_user.cliente_id).first()
        if client:
            query = query.filter(models.Card.CustCode == client.code)
            
    if search_term:
        query = query.filter(
            (models.Card.Name.ilike(f"%{search_term}%")) |
            (models.Card.Comment.ilike(f"%{search_term}%"))
        )
    if Status:
        query = query.filter(models.Card.State == Status)
    if Priority:
        query = query.filter(models.Card.Priority == Priority)
    if CustCode:
        query = query.filter(models.Card.CustCode == CustCode)
    if start_date and hasattr(models.Card, 'date_column'):
        query = query.filter(models.Card.date_column >= start_date)
    if end_date and hasattr(models.Card, 'date_column'):
        query = query.filter(models.Card.date_column <= end_date)
    
    # Order by internalId descending to show newest tickets first
    query = query.order_by(models.Card.internalId.desc())
    
    cards = query.offset(skip).limit(limit).all()
    return cards

@router.get("/cards/{card_id}", response_model=CardDetailResponse, tags=["Cards"])
def read_card(card_id: int, db: Session = Depends(get_db)):
    db_card = db.query(models.Card).options(joinedload(models.Card.cliente)).filter(models.Card.internalId == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    print(f"DEBUG: Fetched card from DB. db_card.assign = '{db_card.assign}'")

    response = CardDetailResponse.from_orm(db_card)
    if db_card.cliente:
        response.customer_internal_id = db_card.cliente.id
        
    print(f"DEBUG: Pydantic response object created. response.assign = '{response.assign}'")
    
    return response

@router.put("/cards/{card_id}", response_model=CardResponse, tags=["Cards"])
def update_card(card_id: int, card: CardBase, db: Session = Depends(get_db)):
    db_card = db.query(models.Card).filter(models.Card.internalId == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card not found")

    update_data = card.dict(exclude_unset=True)

    if "State" in update_data and update_data["State"] == "Terminado":
        update_data["State"] = "Cerrado"

    if "State" in update_data and update_data["State"] != db_card.State:
        db_card.state_last_changed_date = datetime.now(timezone.utc)
        current_state = db_card.State
        
        if current_state == "Terminado":
            current_state = "Cerrado"
        
        new_state = update_data["State"]

        if current_state in TRANSITION_RULES:
            if new_state not in TRANSITION_RULES[current_state]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Transición de estado inválida: de '{current_state}' a '{new_state}' no está permitida."
                )

    for key, value in update_data.items():
        setattr(db_card, key, value)

    db.commit()
    db.refresh(db_card)
    return db_card
