from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from .. import models
from ..database import get_db # Use centralized get_db
from .users_api import get_current_user # Use centralized get_current_user

router = APIRouter(
    prefix="/api",
    tags=["Clientes"]
)

# Pydantic Models (Schemas)
class ClienteBase(BaseModel):
    nombre: str | None = None
    razon_social: str
    ruc: str | None = None
    contacto: str | None = None
    email: str | None = None
    estado: int | None = None # Changed from str | None to int | None
    support_hours: float = 0.0
    support_hours_consumed: float = 0.0
    encargados: str | None = None

class ClienteCreate(ClienteBase):
    pass

class Cliente(ClienteBase):
    id: int
    code: str | None = None
    # Omitting relationships for brevity in list views
    # actividades: list = []
    # proyectos: list = []

    class Config:
        from_attributes = True

class ClienteWithTicketStatus(Cliente):
    has_rejected_tickets: bool = False
    has_pending_tickets: bool = False
    has_approved_tickets: bool = False
    encargados: str | None = None

class SupportHoursUpdateRequest(BaseModel):
    support_hours: float

# CRUD Endpoints for Clientes

@router.post("/clientes/", response_model=Cliente, tags=["Clientes"])
def create_cliente(cliente: ClienteCreate, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Not authorized to create clients")

    if cliente.ruc:
        db_cliente_by_ruc = db.query(models.Cliente).filter(models.Cliente.ruc == cliente.ruc).first()
        if db_cliente_by_ruc:
            raise HTTPException(status_code=400, detail="RUC already registered")
    
    if cliente.email:
        db_cliente_by_email = db.query(models.Cliente).filter(models.Cliente.email == cliente.email).first()
        if db_cliente_by_email:
            raise HTTPException(status_code=400, detail="Email already registered")

    db_cliente = models.Cliente(**cliente.dict())
    db.add(db_cliente)
    db.commit()
    db.refresh(db_cliente)
    return db_cliente

@router.get("/clientes/", response_model=List[ClienteWithTicketStatus], tags=["Clientes"])
def read_clientes(skip: int = 0, limit: int = 1000, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    # All authenticated users can view clients
    clientes = db.query(models.Cliente).offset(skip).limit(limit).all()
    
    clientes_with_status = []
    for cliente in clientes:
        # Query for tickets related to this client
        client_tickets = db.query(models.Card).filter(models.Card.CustCode == cliente.code).all()

        has_rejected = False
        has_pending = False
        has_approved = False

        for ticket in client_tickets:
            if ticket.AdditionalHoursStatus == 'Rechazado':
                has_rejected = True
            elif ticket.AdditionalHoursStatus == 'Pendiente de Aprobacion':
                has_pending = True
            elif ticket.AdditionalHoursStatus == 'Aprobado':
                has_approved = True
        
        clientes_with_status.append(ClienteWithTicketStatus(
            id=cliente.id,
            code=cliente.code,
            nombre=cliente.nombre,
            razon_social=cliente.razon_social,
            ruc=cliente.ruc,
            contacto=cliente.contacto,
            email=cliente.email,
            estado=cliente.estado,
            support_hours=cliente.support_hours,
            support_hours_consumed=cliente.support_hours_consumed,
            encargados=cliente.encargados,
            has_rejected_tickets=has_rejected,
            has_pending_tickets=has_pending,
            has_approved_tickets=has_approved
        ))
    return clientes_with_status

@router.get("/clientes/{cliente_id}", response_model=Cliente, tags=["Clientes"])
def read_cliente(cliente_id: int, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    # All authenticated users can view a single client
    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if db_cliente is None:
        raise HTTPException(status_code=404, detail="Cliente not found")
    return db_cliente

@router.put("/clientes/{cliente_id}", response_model=Cliente, tags=["Clientes"])
def update_cliente(cliente_id: int, cliente: ClienteCreate, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Not authorized to update clients")

    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if db_cliente is None:
        raise HTTPException(status_code=404, detail="Cliente not found")
    
    update_data = cliente.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_cliente, key, value)
        
    db.commit()
    db.refresh(db_cliente)
    return db_cliente

@router.put("/clientes/{cliente_id}/support-hours", response_model=Cliente, tags=["Clientes"])
def update_support_hours(cliente_id: int, hours_update: SupportHoursUpdateRequest, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Not authorized to update support hours")

    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if db_cliente is None:
        raise HTTPException(status_code=404, detail="Cliente not found")

    db_cliente.support_hours = hours_update.support_hours
    db.commit()
    db.refresh(db_cliente)
    return db_cliente

@router.delete("/clientes/{cliente_id}", response_model=Cliente, tags=["Clientes"])
def delete_cliente(cliente_id: int, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Not authorized to delete clients")

    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if db_cliente is None:
        raise HTTPException(status_code=404, detail="Cliente not found")
    db.delete(db_cliente)
    db.commit()
    return db_cliente

class ClienteSearchResponse(BaseModel):
    id: int
    code: str | None = None
    nombre: str | None = None
    razon_social: str
    ruc: str | None = None

    class Config:
        from_attributes = True

@router.get("/clientes/search/", response_model=List[ClienteSearchResponse], tags=["Clientes"])

def search_clientes(q: str, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):

    """

    Search for clientes by code, nombre (FantasyName) or ruc (TaxRegNr).

    """

    print(f"Client search query received: {q}") # Debugging

    search = f"%{q}%"

    clientes = db.query(models.Cliente).filter(

        (models.Cliente.code.ilike(search)) |

        (models.Cliente.nombre.ilike(search)) |

        (models.Cliente.ruc.ilike(search))

    ).limit(10).all()

    print(f"Clients found: {clientes}") # Debugging

    return clientes

class ClienteUpdate(BaseModel):
    nombre: str | None = None
    razon_social: str | None = None
    ruc: str | None = None
    contacto: str | None = None
    email: str | None = None
    estado: int | None = None
    support_hours: float | None = None
    support_hours_consumed: float | None = None
    encargados: str | None = None

@router.patch("/clientes/{cliente_id}", response_model=Cliente, tags=["Clientes"])
def patch_cliente(cliente_id: int, cliente_update: ClienteUpdate, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Not authorized to update clients")

    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if db_cliente is None:
        raise HTTPException(status_code=404, detail="Cliente not found")
    
    update_data = cliente_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_cliente, key, value)
        
    db.commit()
    db.refresh(db_cliente)
    return db_cliente
