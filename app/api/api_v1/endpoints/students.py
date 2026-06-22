from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, cast, Float
from typing import List
from uuid import UUID
import asyncio
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
    from sqlalchemy.orm import selectinload
    from app.db.models import Student, Enrollment, Batch, Course
    
    result = await db.execute(
        select(Student)
        .options(
            selectinload(Student.user),
            selectinload(Student.parent),
            selectinload(Student.enrollments).selectinload(Enrollment.batch).selectinload(Batch.course)
        )
        .offset(skip)
        .limit(limit)
    )
    students = result.scalars().all()
    
    response_data = []
    for s in students:
        # Resolve registered course names from student enrollments
        courses_list = []
        for e in s.enrollments:
            if e.batch and e.batch.course:
                courses_list.append(e.batch.course.name)
        
        # Deduplicate courses
        courses_list = list(set(courses_list))
        
        # Get email and phone from student's own user record or fall back to parent's
        email = s.user.email if s.user else (s.parent.email if s.parent else None)
        phone = s.user.phone if s.user else (s.parent.phone if s.parent else None)
        
        response_data.append({
            "id": s.id,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "date_of_birth": s.date_of_birth,
            "parent_id": s.parent_id,
            "user_id": s.user_id,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "email": email,
            "phone": phone,
            "courses": courses_list
        })
        
    return response_data

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

@router.get("/summary/{user_id}")
async def get_student_summary(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns a combined stats summary for a student by their user_id.

    Runs attendance and quiz queries in PARALLEL (asyncio.gather) so the
    frontend only needs ONE network round-trip to get all enriched stats.
    Used by the Fee Details row popup to reconcile background data.
    """
    from app.db.models import Student, Attendance, AttendanceStatus, QuizAttempt

    # ── 1. Look up the student profile ────────────────────────────────────────
    student_res = await db.execute(
        select(Student).where(Student.user_id == user_id)
    )
    student = student_res.scalars().first()

    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")

    student_id = student.id
    joined_date = student.created_at.isoformat() if student.created_at else None

    # ── 2. Run attendance + quiz queries IN PARALLEL ───────────────────────────
    async def get_attendance():
        total_res = await db.execute(
            select(func.count(Attendance.id)).where(Attendance.student_id == student_id)
        )
        present_res = await db.execute(
            select(func.count(Attendance.id)).where(
                Attendance.student_id == student_id,
                Attendance.status == AttendanceStatus.present
            )
        )
        total = total_res.scalar() or 0
        present = present_res.scalar() or 0
        rate = round((present / total * 100)) if total > 0 else None
        return {"total": total, "present": present, "rate": rate}

    async def get_quiz_stats():
        res = await db.execute(
            select(
                func.count(QuizAttempt.id).label("count"),
                func.avg(
                    case(
                        (QuizAttempt.max_score > 0,
                         cast(QuizAttempt.total_score, Float) / QuizAttempt.max_score),
                        else_=0
                    )
                ).label("avg_ratio")
            ).where(QuizAttempt.student_id == student_id)
        )
        row = res.first()
        count = row.count or 0
        avg_pct = round((row.avg_ratio or 0) * 100) if count > 0 else None
        return {"count": count, "avg_pct": avg_pct}

    attendance, quiz = await asyncio.gather(get_attendance(), get_quiz_stats())

    return {
        "student_id": str(student_id),
        "user_id": str(user_id),
        "joined_date": joined_date,
        "attendance": attendance,
        "quiz": quiz,
    }

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
