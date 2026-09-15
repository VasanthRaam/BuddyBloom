from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from uuid import UUID
from app.db.database import get_db
from app.db.models import User, UserRole, Batch, Course, Enrollment, Student

router = APIRouter()

@router.get("/")
async def get_teachers(db: AsyncSession = Depends(get_db)):
    """Get all approved teachers."""
    query = select(User).where(User.role == UserRole.teacher, User.is_approved == True)
    result = await db.execute(query)
    teachers = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "full_name": t.full_name,
            "email": t.email,
            "phone": t.phone,
            "education_qualification": t.education_qualification,
            "profile_picture": t.profile_picture,
        } for t in teachers
    ]

@router.get("/{teacher_id}/board")
async def get_teacher_board(teacher_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all courses and students for a specific teacher."""
    # Verify teacher
    t_query = select(User).where(User.id == teacher_id, User.role == UserRole.teacher)
    t_res = await db.execute(t_query)
    teacher = t_res.scalars().first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Get batches assigned to this teacher
    b_query = select(Batch).options(selectinload(Batch.course)).where(Batch.teacher_id == teacher_id)
    b_res = await db.execute(b_query)
    batches = b_res.scalars().all()

    board_data = []
    
    # Group by course
    course_map = {}
    for b in batches:
        if b.course_id not in course_map:
            course_map[b.course_id] = {
                "course_id": str(b.course_id),
                "course_name": b.course.name,
                "batches": [],
                "total_students": 0,
                "students": []
            }
        
        # Get students in this batch
        s_query = select(Student).join(Enrollment).where(Enrollment.batch_id == b.id).options(selectinload(Student.user))
        s_res = await db.execute(s_query)
        students = s_res.scalars().all()
        
        student_list = []
        for s in students:
            # We want unique students per course, check if already added
            if not any(existing_s['id'] == str(s.id) for existing_s in course_map[b.course_id]["students"]):
                student_list.append({
                    "id": str(s.id),
                    "user_id": str(s.user_id),
                    "first_name": s.first_name,
                    "last_name": s.last_name,
                    "email": s.user.email if s.user else None,
                    "phone": s.user.phone if s.user else None,
                    "profile_picture": s.user.profile_picture if s.user else None,
                })
            
        course_map[b.course_id]["batches"].append({
            "batch_id": str(b.id),
            "batch_name": b.name,
            "student_count": len(students)
        })
        course_map[b.course_id]["students"].extend(student_list)
        course_map[b.course_id]["total_students"] += len(student_list)

    return list(course_map.values())
