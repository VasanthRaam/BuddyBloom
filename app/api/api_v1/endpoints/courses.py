from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.db.database import get_db
from app.db.models import Course, Batch, UserRole
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/")
async def get_courses(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    role = current_user.get("role")
    user_id = current_user.get("id")
    
    if role == UserRole.admin:
        query = select(Course)
    elif role == UserRole.teacher:
        # Get courses linked to batches assigned to this teacher
        query = select(Course).distinct().join(Batch).where(Batch.teacher_id == user_id)
    else:
        # Students/Parents see courses they are enrolled in
        from app.db.models import Enrollment, Student
        query = select(Course).distinct().join(Batch).join(Enrollment).join(Student).where(Student.user_id == user_id if role == "student" else Student.parent_id == user_id)
        
    result = await db.execute(query)
    courses = result.scalars().all()
    
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "description": c.description
        } for c in courses
    ]
