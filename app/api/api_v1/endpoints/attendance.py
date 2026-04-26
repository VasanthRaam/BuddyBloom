from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from uuid import UUID
from datetime import date

from app.db.database import get_db
from app.schemas.attendance import AttendanceBulkCreate, AttendanceResponse
from app.services.attendance_service import AttendanceService
from app.api.deps import get_current_user, RequireRole

router = APIRouter()

@router.post("/bulk", response_model=List[AttendanceResponse])
async def mark_bulk_attendance(
    attendance_in: AttendanceBulkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["teacher", "admin"]))
):
    """
    Mark attendance for a batch of students.
    Only accessible by teachers and admins.
    """
    try:
        records = await AttendanceService.mark_bulk_attendance(db=db, attendance_in=attendance_in)
        return records
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[AttendanceResponse])
async def get_attendance(
    student_id: Optional[UUID] = Query(None, description="Filter by student ID"),
    batch_id: Optional[UUID] = Query(None, description="Filter by batch ID"),
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    end_date: Optional[date] = Query(None, description="Filter by end date"),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get attendance records.
    Parents and students can view attendance. Teachers and admins can view all.
    """
    role = current_user.get("role")
    
    # Simple role-based data isolation
    if role == "student":
        from app.db.models import Student
        res = await db.execute(select(Student).where(Student.user_id == current_user["id"]))
        student = res.scalars().first()
        if student:
            student_id = student.id
    elif role == "parent":
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id is required for parents.")
            
    records = await AttendanceService.get_attendance(
        db=db,
        student_id=student_id,
        batch_id=batch_id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit
    )
    return records

@router.get("/holidays", response_model=List[dict])
async def get_holidays(
    db: AsyncSession = Depends(get_db)
):
    """Fetch all academy holidays."""
    from app.db.models import AcademyHoliday
    result = await db.execute(select(AcademyHoliday).order_by(AcademyHoliday.date.desc()))
    return result.scalars().all()

@router.post("/holidays", status_code=201)
async def mark_holiday(
    holiday_date: date,
    description: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["admin"]))
):
    """Mark a specific date as an academy holiday. Only Admins."""
    from app.db.models import AcademyHoliday
    
    # Check if exists
    res = await db.execute(select(AcademyHoliday).where(AcademyHoliday.date == holiday_date))
    if res.scalars().first():
        raise HTTPException(status_code=400, detail="This date is already marked as a holiday.")
        
    db_holiday = AcademyHoliday(
        date=holiday_date,
        description=description,
        created_by=current_user["id"]
    )
    db.add(db_holiday)
    await db.commit()
    return {"message": "Academy holiday marked successfully", "date": holiday_date}

@router.delete("/holidays/{holiday_date}")
async def remove_holiday(
    holiday_date: date,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["admin"]))
):
    """Remove an academy holiday. Only Admins."""
    from app.db.models import AcademyHoliday
    from sqlalchemy import delete
    
    await db.execute(delete(AcademyHoliday).where(AcademyHoliday.date == holiday_date))
    await db.commit()
    return {"message": "Holiday removed"}
