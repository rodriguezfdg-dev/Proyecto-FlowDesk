from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from .. import models
from ..database import get_db
from .users_api import get_current_user

router = APIRouter(
    prefix="/api/settings",
    tags=["Settings - Attention Flow"]
)

# Pydantic Schema for the settings
class AttentionFlowSchema(BaseModel):
    max_time_new: int
    max_time_pending: int
    max_time_testing: int
    max_time_waiting: int
    max_time_priority_low: Optional[int] = 0
    max_time_priority_medium: Optional[int] = 0
    max_time_priority_high: Optional[int] = 0
    max_time_priority_critical: Optional[int] = 0

    class Config:
        from_attributes = True

# Helper function to get the settings record, creating it if it doesn't exist
def get_or_create_settings(db: Session):
    settings = db.query(models.AttentionFlowSettings).first()
    if not settings:
        settings = models.AttentionFlowSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

@router.get("/attention-flow", response_model=AttentionFlowSchema)
def get_attention_flow_settings(
    db: Session = Depends(get_db), 
    current_user: models.PersonOfCustomer = Depends(get_current_user)
):
    if current_user.roll != '1':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    
    settings = get_or_create_settings(db)
    return settings

@router.put("/attention-flow", response_model=AttentionFlowSchema)
def update_attention_flow_settings(
    settings_data: AttentionFlowSchema,
    db: Session = Depends(get_db),
    current_user: models.PersonOfCustomer = Depends(get_current_user)
):
    if current_user.roll != '1':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    settings = get_or_create_settings(db)
    
    settings.max_time_new = settings_data.max_time_new
    settings.max_time_pending = settings_data.max_time_pending
    settings.max_time_testing = settings_data.max_time_testing
    settings.max_time_waiting = settings_data.max_time_waiting
    settings.max_time_priority_low = settings_data.max_time_priority_low
    settings.max_time_priority_medium = settings_data.max_time_priority_medium
    settings.max_time_priority_high = settings_data.max_time_priority_high
    settings.max_time_priority_critical = settings_data.max_time_priority_critical
    
    db.commit()
    db.refresh(settings)
    return settings
