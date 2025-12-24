from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import date

from .. import models
from ..database import SessionLocal

router = APIRouter()

# Pydantic Models (Schemas)
class ActividadBase(BaseModel):
    titulo: str
    descripcion: str
    prioridad: str
    estado: str
    cliente_id: int

class ActividadCreate(ActividadBase):
    fecha_creacion: date

class ActividadResponse(ActividadBase):
    id: int
    
    class Config:
        from_attributes = True

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# CRUD Endpoints for Tickets

@router.post("/actividades/", response_model=ActividadResponse, tags=["Actividades"])
def create_actividad(actividad: ActividadCreate, db: Session = Depends(get_db)):
    
    priority_mapping = {
        "Baja": 1,
        "Media": 2,
        "Alta": 3,
        "Crítica": 4
    }
    
    db_actividad_data = actividad.dict()
    db_actividad_data['prioridad'] = priority_mapping.get(actividad.prioridad, 1) # Default to 'Baja' if not found

    db_actividad = models.Actividad(**db_actividad_data)
    db.add(db_actividad)
    db.commit()
    db.refresh(db_actividad)
    return db_actividad

@router.get("/actividades/", response_model=List[ActividadResponse], tags=["Actividades"])
def read_actividades(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    actividades = db.query(models.Actividad).offset(skip).limit(limit).all()
    return actividades

@router.get("/actividades/{actividad_id}", response_model=ActividadResponse, tags=["Actividades"])
def read_actividad(actividad_id: int, db: Session = Depends(get_db)):
    db_actividad = db.query(models.Actividad).filter(models.Actividad.id == actividad_id).first()
    if db_actividad is None:
        raise HTTPException(status_code=404, detail="Actividad not found")
    return db_actividad

@router.put("/actividades/{actividad_id}", response_model=ActividadResponse, tags=["Actividades"])
def update_actividad(actividad_id: int, actividad: ActividadCreate, db: Session = Depends(get_db)):
    db_actividad = db.query(models.Actividad).filter(models.Actividad.id == actividad_id).first()
    if db_actividad is None:
        raise HTTPException(status_code=404, detail="Actividad not found")
    for var, value in vars(actividad).items():
        setattr(db_actividad, var, value) if value else None
    db.commit()
    db.refresh(db_actividad)
    return db_actividad

@router.delete("/actividades/{actividad_id}", response_model=ActividadResponse, tags=["Actividades"])
def delete_actividad(actividad_id: int, db: Session = Depends(get_db)):
    db_actividad = db.query(models.Actividad).filter(models.Actividad.id == actividad_id).first()
    if db_actividad is None:
        raise HTTPException(status_code=404, detail="Actividad not found")
    db.delete(db_actividad)
    db.commit()
    return db_actividad
