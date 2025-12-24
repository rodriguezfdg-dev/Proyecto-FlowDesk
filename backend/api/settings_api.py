from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from .. import models
from ..database import get_db
from .users_api import get_current_user # Import the centralized dependency

router = APIRouter()

# Pydantic Models (Schemas)
class SmtpSettingsBase(BaseModel):
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True
    use_ssl: bool = False

class SmtpSettingsCreate(SmtpSettingsBase):
    pass

class SmtpSettingsResponse(SmtpSettingsBase):
    id: int

    class Config:
        from_attributes = True

# CRUD Endpoints for SMTP Settings

@router.post("/settings/smtp", response_model=SmtpSettingsResponse, tags=["Settings"])
def create_smtp_settings(settings: SmtpSettingsCreate, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Not authorized to configure SMTP settings")
    
    existing_settings = db.query(models.SmtpSettings).first()
    if existing_settings:
        raise HTTPException(status_code=400, detail="SMTP settings already exist. Use PUT to update.")
    
    db_settings = models.SmtpSettings(**settings.dict())
    db.add(db_settings)
    db.commit()
    db.refresh(db_settings)
    return db_settings

@router.get("/settings/smtp", response_model=SmtpSettingsResponse, tags=["Settings"])
def get_smtp_settings(db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Not authorized to view SMTP settings")
        
    settings = db.query(models.SmtpSettings).first()
    if settings is None:
        raise HTTPException(status_code=404, detail="SMTP settings not found")
    return settings

@router.put("/settings/smtp", response_model=SmtpSettingsResponse, tags=["Settings"])
def update_smtp_settings(settings: SmtpSettingsCreate, db: Session = Depends(get_db), current_user: models.PersonOfCustomer = Depends(get_current_user)):
    if current_user.roll != '1':
        raise HTTPException(status_code=403, detail="Not authorized to update SMTP settings")

    db_settings = db.query(models.SmtpSettings).first()
    if db_settings is None:
        raise HTTPException(status_code=404, detail="SMTP settings not found. Use POST to create.")
    
    for key, value in settings.dict().items():
        setattr(db_settings, key, value)
    
    db.commit()
    db.refresh(db_settings)
    return db_settings
