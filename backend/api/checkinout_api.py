# backend/api/checkinout_api.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func
from pydantic import BaseModel
from typing import List
from datetime import date, time

from backend.database import get_db
from backend.models import CheckInOut

# Pydantic models for request and response
class AttendanceRecord(BaseModel):
    emp: str
    chDate: date
    chTime: time
    clock: str | None = None

class BulkAttendanceRequest(BaseModel):
    records: List[AttendanceRecord]
    user: str
    office: str
    computer: str

router = APIRouter(
    prefix="/api/checkinout",
    tags=["CheckInOut"]
)

@router.get("/last-serial")
async def get_last_serial_number(db: Session = Depends(get_db)):
    """
    Gets the last (highest) serial number from the CheckInOut table.
    """
    last_ser_nr = db.query(func.max(CheckInOut.SerNr)).scalar()
    return {"last_serial_number": last_ser_nr or 0}

@router.post("/bulk")
async def bulk_insert_attendance(request: BulkAttendanceRequest, db: Session = Depends(get_db)):
    """
    Inserts a bulk list of attendance records, avoiding duplicates.
    """
    inserted_count = 0
    new_records = []
    
    # Get the last serial number to start incrementing from
    last_ser_nr = db.query(func.max(CheckInOut.SerNr)).scalar() or 0
    current_ser_nr = last_ser_nr + 1

    # Create a set of existing records for efficient lookup
    existing_records = {
        (r.Employee, r.attendance_date, r.attendance_time) 
        for r in db.query(CheckInOut.Employee, CheckInOut.attendance_date, CheckInOut.attendance_time).all()
    }

    today = date.today()
    now = time()

    for record in request.records:
        record_tuple = (record.emp, record.chDate, record.chTime)
        if record_tuple not in existing_records:
            new_db_record = CheckInOut(
                SerNr=current_ser_nr,
                user_name=request.user,
                Office=request.office,
                Computer=request.computer,
                Employee=record.emp,
                attendance_date=record.chDate,
                attendance_time=record.chTime,
                BiometricClock=record.clock,
                transaction_date=today,
                transaction_time=now
            )
            new_records.append(new_db_record)
            existing_records.add(record_tuple) # Add to set to handle duplicates within the same request
            current_ser_nr += 1
    
    if new_records:
        try:
            db.add_all(new_records)
            db.commit()
            inserted_count = len(new_records)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {e}"
            )

    return {"message": f"{inserted_count} records inserted successfully.", "inserted_count": inserted_count}
