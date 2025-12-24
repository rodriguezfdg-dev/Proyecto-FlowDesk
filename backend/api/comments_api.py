from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime, time

from .. import models
from ..database import SessionLocal

router = APIRouter(
    prefix="/api",
    tags=["Comments"]
)

# Pydantic Models (Schemas)
class CommentBase(BaseModel):
    comment: str

class CommentCreate(CommentBase):
    user: str

class CommentResponse(CommentBase):
    id: int
    date_column: Optional[date] = None
    time_column: Optional[time] = None
    user: Optional[str] = None

    class Config:
        from_attributes = True

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Endpoints for Comments

@router.get("/cards/{card_id}/comments/", response_model=List[CommentResponse], tags=["Comments"])
def read_comments_for_card(card_id: int, db: Session = Depends(get_db)):
    comments = db.query(models.CardsEventRow).filter(models.CardsEventRow.master_id == card_id).all()
    return comments

@router.post("/cards/{card_id}/comments/", response_model=CommentResponse, tags=["Comments"])
def create_comment_for_card(card_id: int, comment: CommentCreate, db: Session = Depends(get_db)):
    db_comment = models.CardsEventRow(
        master_id=card_id,
        comment=comment.comment,
        date_column=datetime.now().date(),
        time_column=datetime.now().time(),
        user=comment.user
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment
