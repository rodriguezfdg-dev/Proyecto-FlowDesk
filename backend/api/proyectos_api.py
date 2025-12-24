from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import date

from .. import models
from ..database import get_db
from .users_api import get_current_user

router = APIRouter(
    prefix="/api",
    tags=["Proyectos"]
)

# Pydantic Models (Schemas)
class ProyectoBase(BaseModel):
    nombre: str
    descripcion: str | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    fecha_limite: date | None = None
    presupuesto: float | None = None
    estado: str | int | None = None
    cliente_id: int | None = None  # Made optional to avoid validation errors

class ProyectoCreate(ProyectoBase):
    pass

class Proyecto(ProyectoBase):
    id: int

    class Config:
        from_attributes = True


# CRUD Endpoints for Proyectos

@router.post("/proyectos/", response_model=Proyecto, tags=["Proyectos"])
def create_proyecto(proyecto: ProyectoCreate, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    db_proyecto = models.Proyecto(**proyecto.dict())
    db.add(db_proyecto)
    db.commit()
    db.refresh(db_proyecto)
    return db_proyecto

@router.get("/proyectos/", response_model=List[Proyecto], tags=["Proyectos"])
def read_proyectos(
    skip: int = 0, 
    limit: int = 100, 
    cliente_id: int | None = None,
    active_date: date | None = None,
    db: Session = Depends(get_db), 
    current_user: models.PersonOfCustomer = Depends(get_current_user)
):
    query = db.query(models.Proyecto)
    
    if cliente_id:
        # The Project table uses the Client Code (CustCode), not the internalId.
        # We need to fetch the client first to get their code.
        cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
        if cliente and cliente.code:
            # Filter by the client's code
            query = query.filter(models.Proyecto.cliente_id == cliente.code)
        else:
            # If client not found or has no code, return empty or filter by ID directly (fallback)
            query = query.filter(models.Proyecto.cliente_id == cliente_id)
        
    if active_date:
        # Filter projects active on the given date
        # StartDate <= active_date AND (EndDate >= active_date OR EndDate is NULL)
        query = query.filter(
            models.Proyecto.fecha_inicio <= active_date,
            (models.Proyecto.fecha_fin >= active_date) | (models.Proyecto.fecha_fin == None)
        )
        
    proyectos = query.offset(skip).limit(limit).all()
    return proyectos

@router.get("/proyectos/{proyecto_id}", response_model=Proyecto, tags=["Proyectos"])
def read_proyecto(proyecto_id: int, db: Session = Depends(get_db)):
    db_proyecto = db.query(models.Proyecto).filter(models.Proyecto.id == proyecto_id).first()
    if db_proyecto is None:
        raise HTTPException(status_code=404, detail="Proyecto not found")
    return db_proyecto

@router.put("/proyectos/{proyecto_id}", response_model=Proyecto, tags=["Proyectos"])
def update_proyecto(proyecto_id: int, proyecto: ProyectoCreate, db: Session = Depends(get_db)):
    db_proyecto = db.query(models.Proyecto).filter(models.Proyecto.id == proyecto_id).first()
    if db_proyecto is None:
        raise HTTPException(status_code=404, detail="Proyecto not found")
    for var, value in vars(proyecto).items():
        setattr(db_proyecto, var, value) if value else None
    db.commit()
    db.refresh(db_proyecto)
    return db_proyecto

@router.delete("/proyectos/{proyecto_id}", response_model=Proyecto, tags=["Proyectos"])
def delete_proyecto(proyecto_id: int, db: Session = Depends(get_db)):
    db_proyecto = db.query(models.Proyecto).filter(models.Proyecto.id == proyecto_id).first()
    if db_proyecto is None:
        raise HTTPException(status_code=404, detail="Proyecto not found")
    db.delete(db_proyecto)
    db.commit()
    return db_proyecto