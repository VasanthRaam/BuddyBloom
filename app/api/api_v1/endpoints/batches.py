from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from uuid import UUID

from app.db.database import get_db
from app.db.models import Batch, Student, Attendance
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/")
async def get_batches(
    course_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    role = current_user.get("role")
    user_id = current_user.get("id")
    
    query = select(Batch)
    if course_id:
        query = query.where(Batch.course_id == course_id)
        
    if role == "teacher":
        query = query.where(Batch.teacher_id == user_id)
    elif role == "student":
        from app.db.models import Enrollment, Student
        query = query.join(Enrollment).join(Student).where(Student.user_id == user_id)
    elif role == "parent":
        from app.db.models import Enrollment, Student
        query = query.join(Enrollment).join(Student).where(Student.parent_id == user_id)

    result = await db.execute(query)
    batches = result.scalars().all()
    
    return [
        {
            "id": str(b.id),
            "name": b.name,
            "course_id": str(b.course_id)
        } for b in batches
    ]

@router.get("/{batch_id}/students")
async def get_batch_students(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    from app.db.models import Student, Enrollment
    
    # Retrieve students enrolled in this specific batch
    query = select(Student).join(Enrollment).where(Enrollment.batch_id == batch_id)
    
    result = await db.execute(query)
    students = result.scalars().all()
    
    return [
        {
            "id": str(s.id),
            "user_id": str(s.user_id),
            "first_name": s.first_name,
            "last_name": s.last_name
        } for s in students
    ]
