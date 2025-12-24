from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List, Optional

print("DEBUG: department_manager_api.py is being imported!")

from .. import models
from ..database import get_db
from .users_api import get_current_user

router = APIRouter(
    prefix="/api",
    tags=["Department Managers"]
)

# Pydantic Models (Schemas)
class DepartmentManagerRowBase(BaseModel):
    department: str
    in_charge_id: int

class DepartmentManagerRowCreate(DepartmentManagerRowBase):
    pass

class DepartmentManagerRowResponse(DepartmentManagerRowBase):
    id: int
    master_id: int
    in_charge_name: str # For display purposes

    class Config:
        from_attributes = True

class DepartmentManagerResponse(BaseModel):
    id: int
    rows: List[DepartmentManagerRowResponse] = []

    class Config:
        from_attributes = True

class DepartmentManagerCreate(BaseModel):
    pass

class DepartmentManagerUpdate(BaseModel):
    pass

# Helper schema to get eligible users for in_charge_id
class EligibleUserResponse(BaseModel):
    id: int
    user: str
    gmail: str

    class Config:
        from_attributes = True


# Dependency to get the single DepartmentManager instance
def get_department_manager_instance(db: Session = Depends(get_db)):
    """Ensures a single DepartmentManager instance exists and returns it."""
    manager_instance = db.query(models.DepartmentManager).first()
    if not manager_instance:
        manager_instance = models.DepartmentManager()
        db.add(manager_instance)
        db.commit()
        db.refresh(manager_instance)
    return manager_instance


@router.get("/department_managers/eligible_users/", response_model=List[EligibleUserResponse])
def get_eligible_users(db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    # Administrators and Developer/Consultors can manage department settings
    if current_user.roll not in ['1', '3']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view eligible users for department managers")

    # Eligible roles are 1 (Administrator), 3 (Developer/consultor), and 4 (Gerente de soporte)
    eligible_users = db.query(models.PersonOfCustomer).filter(
        models.PersonOfCustomer.roll.in_(['1', '3', '4'])
    ).all()
    return eligible_users


@router.get("/department_managers/", response_model=DepartmentManagerResponse)
def get_department_managers_config(
    db: Session = Depends(get_db),
    current_user: models.PersonOfCustomer = Depends(get_current_user),
    manager_instance: models.DepartmentManager = Depends(get_department_manager_instance)
):
    # Administrators and Developer/Consultors can manage department settings
    if current_user.roll not in ['1', '3']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view department managers configuration")

    # Load rows with in_charge_person to get the name
    db.refresh(manager_instance, attribute_names=['rows']) # Ensure rows are loaded
    
    response_rows = []
    for row in manager_instance.rows:
        response_rows.append(DepartmentManagerRowResponse(
            id=row.id,
            master_id=row.master_id,
            department=row.department,
            in_charge_id=row.in_charge_id,
            in_charge_name=row.in_charge_person.user # Use the 'user' field from PersonOfCustomer
        ))
    
    return DepartmentManagerResponse(id=manager_instance.id, rows=response_rows)


@router.post("/department_managers/rows/", response_model=DepartmentManagerRowResponse, status_code=status.HTTP_201_CREATED)
def create_department_manager_row(
    row: DepartmentManagerRowCreate,
    db: Session = Depends(get_db),
    current_user: models.PersonOfCustomer = Depends(get_current_user),
    manager_instance: models.DepartmentManager = Depends(get_department_manager_instance)
):
    # Only administrators can create department manager rows
    if current_user.roll != '1':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to create department manager rows")

    # Verify in_charge_id refers to an eligible person
    in_charge_person = db.query(models.PersonOfCustomer).filter(
        models.PersonOfCustomer.id == row.in_charge_id,
        models.PersonOfCustomer.roll.in_(['1', '3', '4'])
    ).first()
    if not in_charge_person:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="InCharge person not found or not eligible (must be Administrator, Developer/Consultor, or Support Manager)")

    db_row = models.DepartmentManagerRow(
        master_id=manager_instance.id,
        department=row.department,
        in_charge_id=row.in_charge_id,
        in_charge_name=in_charge_person.user # Populate denormalized name
    )
    db.add(db_row)
    db.commit()
    db.refresh(db_row)
    
    return DepartmentManagerRowResponse(
        id=db_row.id,
        master_id=db_row.master_id,
        department=db_row.department,
        in_charge_id=db_row.in_charge_id,
        in_charge_name=in_charge_person.user
    )


@router.put("/department_managers/rows/{row_id}", response_model=DepartmentManagerRowResponse)
def update_department_manager_row(
    row_id: int,
    row_update: DepartmentManagerRowCreate,
    db: Session = Depends(get_db),
    current_user: models.PersonOfCustomer = Depends(get_current_user)
):
    # Only administrators can update department manager rows
    if current_user.roll != '1':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update department manager rows")

    db_row = db.query(models.DepartmentManagerRow).filter(models.DepartmentManagerRow.id == row_id).first()
    if not db_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department Manager Row not found")

    # Verify in_charge_id refers to an eligible person
    in_charge_person = db.query(models.PersonOfCustomer).filter(
        models.PersonOfCustomer.id == row_update.in_charge_id,
        models.PersonOfCustomer.roll.in_(['1', '3', '4'])
    ).first()
    if not in_charge_person:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="InCharge person not found or not eligible (must be Administrator, Developer/Consultor, or Support Manager)")

    db_row.department = row_update.department
    db_row.in_charge_id = row_update.in_charge_id
    db_row.in_charge_name = in_charge_person.user # Update denormalized name

    db.commit()
    db.refresh(db_row)
    
    return DepartmentManagerRowResponse(
        id=db_row.id,
        master_id=db_row.master_id,
        department=db_row.department,
        in_charge_id=db_row.in_charge_id,
        in_charge_name=in_charge_person.user
    )


@router.delete("/department_managers/rows/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department_manager_row(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: models.PersonOfCustomer = Depends(get_current_user)
):
    # Only administrators can delete department manager rows
    if current_user.roll != '1':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete department manager rows")

    db_row = db.query(models.DepartmentManagerRow).filter(models.DepartmentManagerRow.id == row_id).first()
    if not db_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department Manager Row not found")

    db.delete(db_row)
    db.commit()
    return {"message": "Department Manager Row deleted successfully"}