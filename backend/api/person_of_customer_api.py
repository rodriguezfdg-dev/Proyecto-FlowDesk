# backend/api/person_of_customer_api.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from .. import models
from ..database import get_db
from .users_api import get_current_user # Use the centralized dependency

router = APIRouter(
    prefix="/api",
    tags=["Personas"]
)

# Pydantic Models (Schemas) for this API's specific needs
class PersonOfCustomerBase(BaseModel):
    user: str
    gmail: str

class PersonOfCustomer(PersonOfCustomerBase):
    id: int
    is_verified: bool
    roll: str | None = None
    cliente_id: int | None = None
    status: int | None = None
    customername: str | None = None

    class Config:
        from_attributes = True

# CRUD Endpoints for PersonOfCustomer (for admin use)

@router.get("/personas/", response_model=List[PersonOfCustomer], tags=["Personas"])
def read_persons_of_customer(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    # Optional: Add role-based access control if needed
    # if current_user.roll != '1': # Assuming '1' is admin
    #     raise HTTPException(status_code=403, detail="Not authorized to view all users")
    persons = db.query(models.PersonOfCustomer).offset(skip).limit(limit).all()
    return persons

@router.get("/personas/{person_id}", response_model=PersonOfCustomer, tags=["Personas"])
def read_person_of_customer(person_id: int, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    db_person = db.query(models.PersonOfCustomer).filter(models.PersonOfCustomer.id == person_id).first()
    if db_person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return db_person

class RollUpdateRequest(BaseModel):
    roll: str

@router.put("/personas/{person_id}/roll", tags=["Personas"])
def update_person_roll(person_id: int, request: RollUpdateRequest, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Only admins can change user roles")

    db_person = db.query(models.PersonOfCustomer).filter(models.PersonOfCustomer.id == person_id).first()
    if db_person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    db_person.roll = request.roll
    db.commit()

    return {"message": "User roll updated successfully"}

class StatusUpdateRequest(BaseModel):
    status: int

@router.put("/personas/{person_id}/status", tags=["Personas"])
def update_person_status(person_id: int, request: StatusUpdateRequest, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Only admins can change user status")

    db_person = db.query(models.PersonOfCustomer).filter(models.PersonOfCustomer.id == person_id).first()
    if db_person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    db_person.status = request.status
    db.commit()

    return {"message": "User status updated successfully"}

class CustomerNameUpdateRequest(BaseModel):
    customername: str

@router.put("/personas/{person_id}/customername", tags=["Personas"])
def update_person_customername(person_id: int, request: CustomerNameUpdateRequest, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Only admins can change customer name")

    db_person = db.query(models.PersonOfCustomer).filter(models.PersonOfCustomer.id == person_id).first()
    if db_person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    db_person.customername = request.customername
    db.commit()

    return {"message": "Customer name updated successfully"}

class ClienteIdUpdateRequest(BaseModel):
    cliente_id: int

@router.put("/personas/{person_id}/cliente", tags=["Personas"])
def update_person_cliente(person_id: int, request: ClienteIdUpdateRequest, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Only admins can change customer assignment")

    db_person = db.query(models.PersonOfCustomer).filter(models.PersonOfCustomer.id == person_id).first()
    if db_person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    db_person.cliente_id = request.cliente_id
    db.commit()

    return {"message": "Customer assigned successfully"}

@router.delete("/personas/{person_id}", tags=["Personas"])
def delete_person_of_customer(person_id: int, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Only admins can delete users")

    db_person = db.query(models.PersonOfCustomer).filter(models.PersonOfCustomer.id == person_id).first()
    if db_person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    db.delete(db_person)
    db.commit()

    return {"message": "Person deleted successfully"}



