from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
import shutil
import uuid

from .. import models
from ..database import get_db

router = APIRouter(
    prefix="/api",
    tags=["Attachments"]
)

UPLOAD_DIRECTORY = "uploads"

@router.post("/cards/{card_id}/attachments", response_model=List[dict])
async def upload_attachments(
    card_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    db_card = db.query(models.Card).filter(models.Card.internalId == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card not found")

    if not os.path.exists(UPLOAD_DIRECTORY):
        os.makedirs(UPLOAD_DIRECTORY)

    attachments = []
    for file in files:
        # Generate a unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIRECTORY, unique_filename)

        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Create attachment record in the database
        db_attachment = models.TicketAttachment(
            filename=file.filename,
            filepath=file_path,
            filesize=file.size,
            mimetype=file.content_type,
            card_id=card_id
        )
        db.add(db_attachment)
        db.commit()
        db.refresh(db_attachment)
        
        attachments.append({
            "id": db_attachment.id,
            "filename": db_attachment.filename,
            "filesize": db_attachment.filesize,
            "mimetype": db_attachment.mimetype,
            "created_at": db_attachment.created_at
        })

    return attachments

@router.get("/cards/{card_id}/attachments", response_model=List[dict])
def get_attachments_for_card(card_id: int, db: Session = Depends(get_db)):
    db_card = db.query(models.Card).filter(models.Card.internalId == card_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    attachments = []
    for attachment in db_card.attachments:
        attachments.append({
            "id": attachment.id,
            "filename": attachment.filename,
            "filesize": attachment.filesize,
            "mimetype": attachment.mimetype,
            "created_at": attachment.created_at
        })
        
    return attachments

@router.get("/attachments/{attachment_id}")
async def download_attachment(attachment_id: int, db: Session = Depends(get_db)):
    db_attachment = db.query(models.TicketAttachment).filter(models.TicketAttachment.id == attachment_id).first()
    if not db_attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    file_path = db_attachment.filepath
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    return FileResponse(path=file_path, filename=db_attachment.filename)
