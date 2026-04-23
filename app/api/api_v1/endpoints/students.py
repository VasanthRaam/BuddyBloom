from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID
from app.db.database import get_db
from app.schemas.student import StudentResponse, StudentCreate
from app.services.student_service import StudentService
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/", response_model=List[StudentResponse])
async def read_students(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve students. Requires Authentication.
    """
    students = await StudentService.get_students(db, skip=skip, limit=limit)
    return students

@router.post("/", response_model=StudentResponse)
async def create_student(
    student: StudentCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new student. Requires Authentication.
    """
    return await StudentService.create_student(db=db, student=student)

@router.get("/{student_id}", response_model=StudentResponse)
async def read_student(
    student_id: UUID, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific student by ID.
    """
    student = await StudentService.get_student(db, student_id=student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student
