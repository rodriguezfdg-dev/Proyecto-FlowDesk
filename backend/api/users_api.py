# backend/api/users_api.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from backend.database import get_db
from backend.models import PersonOfCustomer, Cliente
from backend import models
from backend.api.auth_api import oauth2_scheme, SECRET_KEY, ALGORITHM

router = APIRouter(
    prefix="/api/users",
    tags=["Users"]
)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(PersonOfCustomer).filter(PersonOfCustomer.user == username).first()
    if user is None:
        raise credentials_exception
    return user

@router.get("/me")
async def read_users_me(current_user: PersonOfCustomer = Depends(get_current_user), db: Session = Depends(get_db)):
    customer_code = None
    if current_user.cliente_id:
        customer = db.query(Cliente).filter(Cliente.id == current_user.cliente_id).first()
        if customer:
            customer_code = customer.code
            
    company_encargados = []
    if customer_code and customer.encargados:
        encargados_list = [name.strip() for name in customer.encargados.split(',') if name.strip()]
        for encargado_name in encargados_list:
            # Find the user to get their ID
            encargado_user = db.query(PersonOfCustomer).filter(PersonOfCustomer.user == encargado_name).first()
            department_name = "General"
            if encargado_user:
                # Find their department
                dept_row = db.query(models.DepartmentManagerRow).filter(
                    models.DepartmentManagerRow.in_charge_id == encargado_user.id
                ).first()
                if dept_row:
                    department_name = dept_row.department
            
            company_encargados.append({
                "username": encargado_name,
                "department": department_name,
                "label": f"{department_name} ({encargado_name})"
            })

    return {
        "username": current_user.user,
        "email": current_user.gmail,
        "roll": current_user.roll,
        "is_verified": current_user.is_verified,
        "customer_id": current_user.cliente_id,
        "customer_code": customer_code,
        "customer_name": customer.razon_social if customer_code else None,
        "status": current_user.status,
        "support_hours": customer.support_hours if customer_code else 0.0,
        "support_hours_consumed": customer.support_hours_consumed if customer_code else 0.0,
        "company_encargados": company_encargados
    }
