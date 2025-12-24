from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from .. import models
from ..database import get_db
from .users_api import get_current_user

router = APIRouter(
    prefix="/api/boards",
    tags=["Boards"]
)

class BoardBase(BaseModel):
    ID: str
    Name: str
    Customer: Optional[str] = None
    Department: Optional[str] = None
    BoardType: Optional[int] = None

class BoardCreate(BoardBase):
    pass

class BoardResponse(BoardBase):
    internalId: int
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[BoardResponse])
def read_boards(
    skip: int = 0, 
    limit: int = 100, 
    customer_code: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.PersonOfCustomer = Depends(get_current_user)
):
    query = db.query(models.Board)
    
    if customer_code:
        query = query.filter(models.Board.Customer == customer_code)
        
    return query.offset(skip).limit(limit).all()

@router.post("/", response_model=BoardResponse)
def create_board(
    board: BoardCreate, 
    db: Session = Depends(get_db),
    current_user: models.PersonOfCustomer = Depends(get_current_user)
):
    # Check if board ID already exists
    existing_board = db.query(models.Board).filter(models.Board.ID == board.ID).first()
    if existing_board:
        raise HTTPException(status_code=400, detail="Board ID already exists")
        
    db_board = models.Board(**board.dict())
    db.add(db_board)
    db.commit()
    db.refresh(db_board)
    return db_board

@router.delete("/{board_id}")
def delete_board(
    board_id: int, 
    db: Session = Depends(get_db),
    current_user: models.PersonOfCustomer = Depends(get_current_user)
):
    db_board = db.query(models.Board).filter(models.Board.internalId == board_id).first()
    if not db_board:
        raise HTTPException(status_code=404, detail="Board not found")
        
    db.delete(db_board)
    db.commit()
    return {"ok": True}
