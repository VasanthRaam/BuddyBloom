from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, cast, Float
from typing import List
from uuid import UUID
import asyncio
from app.db.database import get_db
from app.schemas.student import StudentResponse, StudentCreate, StudentUpdate
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
            "courses": courses_list,
            "mother_name": s.mother_name,
            "father_name": s.father_name,
            "parent_phone_number": s.parent_phone_number,
            "education_qualification": s.user.education_qualification if s.user else None,
            "profile_picture": s.user.profile_picture if s.user else None,
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
        select(Student).where((Student.user_id == user_id) | (Student.id == user_id))
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
                Attendance.status.in_([AttendanceStatus.present, 'present', 'Present', 'PRESENT'])
            )
        )
        total = total_res.scalar() or 0
        present = present_res.scalar() or 0
        rate = round((present / total * 100)) if total > 0 else 100
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

@router.get("/teacher-students")
async def get_teacher_students(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns students enrolled in the calling teacher's batches.
    Same shape as the admin /students/ endpoint.
    """
    from app.db.models import Student, Enrollment, Batch, Course, User as UserModel
    from sqlalchemy.orm import selectinload

    teacher_id = UUID(current_user["id"])

    # Get batches assigned to this teacher
    batch_res = await db.execute(
        select(Batch).where(Batch.teacher_id == teacher_id)
    )
    teacher_batches = batch_res.scalars().all()
    teacher_batch_ids = [b.id for b in teacher_batches]

    if not teacher_batch_ids:
        return []

    # Get students enrolled in those batches
    result = await db.execute(
        select(Student)
        .options(
            selectinload(Student.user),
            selectinload(Student.parent),
            selectinload(Student.enrollments).selectinload(Enrollment.batch).selectinload(Batch.course)
        )
        .join(Enrollment, Enrollment.student_id == Student.id)
        .where(Enrollment.batch_id.in_(teacher_batch_ids))
        .distinct()
    )
    students = result.scalars().unique().all()

    response_data = []
    for s in students:
        courses_list = []
        for e in s.enrollments:
            if e.batch and e.batch.course:
                courses_list.append(e.batch.course.name)
        courses_list = list(set(courses_list))

        email = s.user.email if s.user else (s.parent.email if s.parent else None)
        phone = s.user.phone if s.user else (s.parent.phone if s.parent else None)

        response_data.append({
            "id": str(s.id),
            "first_name": s.first_name,
            "last_name": s.last_name,
            "date_of_birth": str(s.date_of_birth) if s.date_of_birth else None,
            "parent_id": str(s.parent_id) if s.parent_id else None,
            "user_id": str(s.user_id) if s.user_id else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "email": email,
            "phone": phone,
            "courses": courses_list,
            "mother_name": s.mother_name,
            "father_name": s.father_name,
            "parent_phone_number": s.parent_phone_number,
            "education_qualification": s.user.education_qualification if s.user else None,
            "profile_picture": s.user.profile_picture if s.user else None,
        })

    return response_data


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

@router.put("/{student_id}")
async def update_student(
    student_id: UUID,
    student_in: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update a student's details. Admin or Teacher only.
    """
    if current_user.get("role") not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    from app.db.models import Student, User
    from sqlalchemy.orm import selectinload
    
    result = await db.execute(
        select(Student)
        .options(selectinload(Student.user), selectinload(Student.parent))
        .where(Student.id == student_id)
    )
    student = result.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if student_in.first_name is not None:
        student.first_name = student_in.first_name
    if student_in.last_name is not None:
        student.last_name = student_in.last_name
    if student_in.date_of_birth is not None:
        student.date_of_birth = student_in.date_of_birth
    if student_in.mother_name is not None:
        student.mother_name = student_in.mother_name
    if student_in.father_name is not None:
        student.father_name = student_in.father_name
    if student_in.parent_phone_number is not None:
        student.parent_phone_number = student_in.parent_phone_number

    if student.user:
        if student_in.first_name is not None or student_in.last_name is not None:
            fn = student_in.first_name if student_in.first_name is not None else student.first_name
            ln = student_in.last_name if student_in.last_name is not None else student.last_name
            student.user.full_name = f"{fn} {ln}".strip()
        if student_in.email is not None:
            student.user.email = student_in.email
        if student_in.phone is not None:
            student.user.phone = student_in.phone

    await db.commit()
    
    # Reload and return
    result = await db.execute(
        select(Student)
        .options(selectinload(Student.user), selectinload(Student.parent))
        .where(Student.id == student_id)
    )
    student = result.scalars().first()
    
    email = student.user.email if student.user else (student.parent.email if student.parent else None)
    phone = student.user.phone if student.user else (student.parent.phone if student.parent else None)
    
    return {
        "id": str(student.id),
        "first_name": student.first_name,
        "last_name": student.last_name,
        "date_of_birth": str(student.date_of_birth) if student.date_of_birth else None,
        "parent_id": str(student.parent_id),
        "user_id": str(student.user_id) if student.user_id else None,
        "email": email,
        "phone": phone,
        "mother_name": student.mother_name,
        "father_name": student.father_name,
        "parent_phone_number": student.parent_phone_number
    }

@router.delete("/{student_id}")
async def delete_student(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a student. Admin only.
    Automatically deletes their associated User record (student login)
    and removes them from Supabase Auth as well.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete students")

    import logging
    from sqlalchemy import delete, update
    from app.db.models import (
        Student, User, PointTransaction, RewardRedemption,
        QuizAttempt, Attendance, Enrollment, FeePayment,
        HomeworkSubmission, Homework, UserPushToken, ChatMessage,
        Notification, LeaveRequest, PendingEnrollment,
        PasswordResetOTP, MobileLoginOTP, PendingRegistration
    )
    from app.core.config import settings
    from supabase import create_client as _cc

    logger = logging.getLogger("app.api.students")

    try:
        # 1. Fetch student record
        result = await db.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalars().first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        user_id_to_delete = student.user_id

        # Fetch user email directly via SQL scalar to prevent lazy-load greenlet errors
        student_email = None
        if user_id_to_delete:
            u_res = await db.execute(select(User.email).where(User.id == user_id_to_delete))
            student_email = u_res.scalar()

        # 2. Clean up student-specific child records via direct SQL deletes
        await db.execute(delete(PointTransaction).where(PointTransaction.student_id == student_id))
        await db.execute(delete(RewardRedemption).where(RewardRedemption.student_id == student_id))
        await db.execute(delete(QuizAttempt).where(QuizAttempt.student_id == student_id))
        await db.execute(delete(Attendance).where(Attendance.student_id == student_id))
        await db.execute(delete(Enrollment).where(Enrollment.student_id == student_id))

        if user_id_to_delete:
            await db.execute(delete(FeePayment).where(FeePayment.user_id == user_id_to_delete))
            await db.execute(delete(HomeworkSubmission).where(HomeworkSubmission.student_id == user_id_to_delete))
            await db.execute(delete(UserPushToken).where(UserPushToken.user_id == user_id_to_delete))
            await db.execute(delete(ChatMessage).where(ChatMessage.user_id == user_id_to_delete))
            await db.execute(delete(Notification).where(Notification.user_id == user_id_to_delete))
            await db.execute(delete(LeaveRequest).where(LeaveRequest.user_id == user_id_to_delete))
            await db.execute(delete(PendingEnrollment).where(PendingEnrollment.user_id == user_id_to_delete))
            
            # Nullify references in Homework, PointTransaction, and Student parent_id
            await db.execute(update(Homework).where(Homework.student_id == user_id_to_delete).values(student_id=None))
            await db.execute(update(PointTransaction).where(PointTransaction.given_by == user_id_to_delete).values(given_by=None))
            await db.execute(update(Student).where(Student.parent_id == user_id_to_delete).values(parent_id=None))

        if student_email:
            await db.execute(delete(PasswordResetOTP).where(PasswordResetOTP.email == student_email))
            await db.execute(delete(PendingRegistration).where(PendingRegistration.email == student_email))

        # 3. Supabase Auth account removal
        if user_id_to_delete and settings.SUPABASE_SERVICE_KEY:
            try:
                admin_client = _cc(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
                admin_client.auth.admin.delete_user(str(user_id_to_delete))
                logger.info(f"[DELETE-STUDENT] Deleted user {user_id_to_delete} from Supabase Auth.")
            except Exception as e:
                logger.info(f"[DELETE-STUDENT] Supabase delete user info: {e}")

        # 4. Direct SQL delete for Student and User records (prevents ORM relationship lazy-loading greenlet errors)
        await db.execute(delete(Student).where(Student.id == student_id))
        
        if user_id_to_delete:
            await db.execute(delete(User).where(User.id == user_id_to_delete))

        await db.commit()
        return {"message": "Student and their login account deleted successfully"}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[DELETE-STUDENT] Delete failed for student_id={student_id}: {exc}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete student: {str(exc)}")
