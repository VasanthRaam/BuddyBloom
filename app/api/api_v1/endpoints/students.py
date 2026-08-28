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
                Attendance.status == AttendanceStatus.present
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
        .where((Student.id == student_id) | (Student.user_id == student_id))
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

# ── Admin: Manually Create Student with Login Credentials ─────────────────────

from pydantic import BaseModel as _BM, EmailStr as _ES
from typing import Optional as _Opt, List as _Lst
import uuid as _uuid_mod


class AdminCreateStudentRequest(_BM):
    first_name: str
    last_name: str
    email: _ES
    password: str
    phone: _Opt[str] = None
    date_of_birth: _Opt[str] = None
    mother_name: _Opt[str] = None
    father_name: _Opt[str] = None
    parent_phone_number: _Opt[str] = None
    batch_ids: _Opt[_Lst[_uuid_mod.UUID]] = []


@router.post("/admin-create")
async def admin_create_student(
    body: AdminCreateStudentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Admin-only: Create a student account with full login credentials.

    Immediately creates the Supabase Auth account (email_confirm=True so no
    email verification needed) and all DB records. The student can log in
    right away and change their password from the Profile screen.

    Returns: { student_id, user_id, email, message }
    """
    import logging
    import uuid as _uuid
    import datetime
    from sqlalchemy import func
    from app.db.models import (
        Student, User, UserRole, Enrollment, Batch,
        PasswordResetOTP, PendingRegistration
    )
    from app.core.config import settings
    from supabase import create_client as _cc

    logger = logging.getLogger("app.api.students")

    # ── 1. Admin guard ────────────────────────────────────────────────────────
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create student accounts directly.")

    # ── 2. Basic input validation ─────────────────────────────────────────────
    if not body.first_name.strip() or not body.last_name.strip():
        raise HTTPException(status_code=400, detail="First name and last name are required.")

    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    try:
        # ── 3. Check email uniqueness in our DB ───────────────────────────────
        existing_user = await db.execute(
            select(User).where(func.lower(User.email) == func.lower(body.email))
        )
        if existing_user.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=f"A user with the email '{body.email}' already exists."
            )

        existing_pending = await db.execute(
            select(PendingRegistration).where(
                func.lower(PendingRegistration.email) == func.lower(body.email),
                PendingRegistration.status == "pending"
            )
        )
        if existing_pending.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=f"A pending registration for '{body.email}' already exists."
            )

        # ── 4. Validate batch_ids if provided ─────────────────────────────────
        if body.batch_ids:
            b_res = await db.execute(
                select(Batch.id).where(Batch.id.in_(body.batch_ids))
            )
            found_batches = b_res.scalars().all()
            if len(found_batches) != len(body.batch_ids):
                raise HTTPException(status_code=400, detail="One or more selected batches are invalid.")

        # ── 5. Create Supabase Auth user (admin API — no email verification) ──
        if not settings.SUPABASE_SERVICE_KEY:
            raise HTTPException(
                status_code=500,
                detail="Supabase service key is not configured. Cannot create auth account."
            )

        admin_supabase = _cc(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        supabase_user_id = None

        try:
            auth_response = admin_supabase.auth.admin.create_user({
                "email": body.email,
                "password": body.password,
                "email_confirm": True,   # skip email confirmation
            })
            supabase_user_id = auth_response.user.id
            logger.info(f"[ADMIN-CREATE-STUDENT] Created Supabase user {supabase_user_id} for {body.email}")
        except Exception as supa_err:
            err_str = str(supa_err).lower()
            if any(k in err_str for k in ["already exists", "already registered", "already been registered"]):
                raise HTTPException(
                    status_code=409,
                    detail=f"An account with email '{body.email}' already exists in the authentication system."
                )
            logger.error(f"[ADMIN-CREATE-STUDENT] Supabase user creation failed: {supa_err}", exc_info=True)
            raise HTTPException(
                status_code=502,
                detail=f"Failed to create authentication account: {str(supa_err)}"
            )

        # ── 6. Parse date_of_birth ─────────────────────────────────────────────
        parsed_dob = None
        if body.date_of_birth:
            try:
                parsed_dob = datetime.datetime.strptime(body.date_of_birth, "%Y-%m-%d").date()
            except ValueError:
                pass  # silently ignore invalid DOB — non-critical

        # ── 7. Create local User record ────────────────────────────────────────
        new_user = User(
            id=supabase_user_id,
            full_name=f"{body.first_name.strip()} {body.last_name.strip()}",
            email=body.email.lower().strip(),
            phone=body.phone,
            role=UserRole.student,
            is_approved=True,
            dob=parsed_dob,
        )
        db.add(new_user)
        await db.flush()  # get new_user.id into session

        # ── 8. Create Student profile ──────────────────────────────────────────
        new_student = Student(
            id=_uuid.uuid4(),
            user_id=new_user.id,
            parent_id=new_user.id,   # self-referencing parent (same as approval flow)
            first_name=body.first_name.strip(),
            last_name=body.last_name.strip(),
            date_of_birth=parsed_dob,
            mother_name=body.mother_name,
            father_name=body.father_name,
            parent_phone_number=body.parent_phone_number,
        )
        db.add(new_student)
        await db.flush()

        # ── 9. Enroll in batches if provided ──────────────────────────────────
        if body.batch_ids:
            for b_id in body.batch_ids:
                enrollment = Enrollment(
                    id=_uuid.uuid4(),
                    student_id=new_student.id,
                    batch_id=b_id,
                )
                db.add(enrollment)

        await db.commit()
        logger.info(
            f"[ADMIN-CREATE-STUDENT] Successfully created student {new_student.id} "
            f"(user {new_user.id}) for {body.email}"
        )

        return {
            "message": "Student account created successfully. The student can log in with the provided credentials.",
            "student_id": str(new_student.id),
            "user_id": str(new_user.id),
            "email": new_user.email,
            "full_name": new_user.full_name,
        }

    except HTTPException:
        await db.rollback()
        # If Supabase user was already created but DB insert failed, clean it up
        if 'supabase_user_id' in dir() and supabase_user_id:
            try:
                admin_supabase.auth.admin.delete_user(str(supabase_user_id))
                logger.info(f"[ADMIN-CREATE-STUDENT] Cleaned up orphaned Supabase user {supabase_user_id}")
            except Exception as cleanup_err:
                logger.warning(f"[ADMIN-CREATE-STUDENT] Failed to clean up Supabase user: {cleanup_err}")
        raise
    except Exception as exc:
        await db.rollback()
        if 'supabase_user_id' in dir() and supabase_user_id:
            try:
                admin_supabase.auth.admin.delete_user(str(supabase_user_id))
                logger.info(f"[ADMIN-CREATE-STUDENT] Cleaned up orphaned Supabase user {supabase_user_id}")
            except Exception as cleanup_err:
                logger.warning(f"[ADMIN-CREATE-STUDENT] Failed to clean up Supabase user: {cleanup_err}")
        logger.error(f"[ADMIN-CREATE-STUDENT] Unexpected error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create student: {str(exc)}")

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
        PasswordResetOTP, MobileLoginOTP, PendingRegistration,
        ProgressTracking
    )
    from app.core.config import settings
    from supabase import create_client as _cc

    logger = logging.getLogger("app.api.students")

    try:
        # 1. Fetch student record matching either Student.id or Student.user_id
        result = await db.execute(
            select(Student).where((Student.id == student_id) | (Student.user_id == student_id))
        )
        student = result.scalars().first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        student_id = student.id  # Bind to actual Student PK for cascading deletes

        user_id_to_delete = student.user_id
        parent_id = student.parent_id

        # Fetch user email directly via SQL scalar to prevent lazy-load greenlet errors
        student_email = None
        if user_id_to_delete:
            u_res = await db.execute(select(User.email).where(User.id == user_id_to_delete))
            student_email = u_res.scalar()

        # 2. Delete all child records that reference student_id
        await db.execute(delete(ProgressTracking).where(ProgressTracking.student_id == student_id))
        await db.execute(delete(PointTransaction).where(PointTransaction.student_id == student_id))
        await db.execute(delete(RewardRedemption).where(RewardRedemption.student_id == student_id))
        await db.execute(delete(QuizAttempt).where(QuizAttempt.student_id == student_id))
        await db.execute(delete(Attendance).where(Attendance.student_id == student_id))
        await db.execute(delete(Enrollment).where(Enrollment.student_id == student_id))
        await db.execute(delete(LeaveRequest).where(LeaveRequest.student_id == student_id))
        await db.execute(delete(PendingEnrollment).where(PendingEnrollment.student_id == student_id))

        # 3. Delete child records that reference user_id
        if user_id_to_delete:
            await db.execute(delete(FeePayment).where(FeePayment.user_id == user_id_to_delete))
            await db.execute(delete(HomeworkSubmission).where(HomeworkSubmission.student_id == user_id_to_delete))
            await db.execute(delete(UserPushToken).where(UserPushToken.user_id == user_id_to_delete))
            await db.execute(delete(ChatMessage).where(ChatMessage.user_id == user_id_to_delete))
            await db.execute(delete(Notification).where(Notification.user_id == user_id_to_delete))
            # Nullify Homework/PointTransaction rows that soft-reference this user
            await db.execute(update(Homework).where(Homework.student_id == user_id_to_delete).values(student_id=None))
            await db.execute(update(PointTransaction).where(PointTransaction.given_by == user_id_to_delete).values(given_by=None))
            # parent_id is NOT NULL — delete any other student records that reference this user as parent
            # (fetch their IDs first so we can cascade-delete their children too)
            orphan_res = await db.execute(
                select(Student.id).where(Student.parent_id == user_id_to_delete, Student.id != student_id)
            )
            orphan_ids = [row[0] for row in orphan_res.fetchall()]
            if orphan_ids:
                await db.execute(delete(ProgressTracking).where(ProgressTracking.student_id.in_(orphan_ids)))
                await db.execute(delete(PointTransaction).where(PointTransaction.student_id.in_(orphan_ids)))
                await db.execute(delete(RewardRedemption).where(RewardRedemption.student_id.in_(orphan_ids)))
                await db.execute(delete(QuizAttempt).where(QuizAttempt.student_id.in_(orphan_ids)))
                await db.execute(delete(Attendance).where(Attendance.student_id.in_(orphan_ids)))
                await db.execute(delete(Enrollment).where(Enrollment.student_id.in_(orphan_ids)))
                await db.execute(delete(LeaveRequest).where(LeaveRequest.student_id.in_(orphan_ids)))
                await db.execute(delete(PendingEnrollment).where(PendingEnrollment.student_id.in_(orphan_ids)))
                await db.execute(delete(Student).where(Student.id.in_(orphan_ids)))
                logger.info(f"[DELETE-STUDENT] Also deleted {len(orphan_ids)} orphaned student(s) sharing same parent.")

        if student_email:
            await db.execute(delete(PasswordResetOTP).where(PasswordResetOTP.email == student_email))
            await db.execute(delete(PendingRegistration).where(PendingRegistration.email == student_email))

        # 4. Delete the Student row FIRST (removes parent_id and user_id FK references)
        await db.execute(delete(Student).where(Student.id == student_id))
        # Flush to apply the student deletion before we try to delete the user
        await db.flush()

        # 5. Supabase Auth account removal (non-blocking — failures are logged, not raised)
        if user_id_to_delete and settings.SUPABASE_SERVICE_KEY:
            try:
                admin_client = _cc(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
                admin_client.auth.admin.delete_user(str(user_id_to_delete))
                logger.info(f"[DELETE-STUDENT] Deleted user {user_id_to_delete} from Supabase Auth.")
            except Exception as e:
                logger.info(f"[DELETE-STUDENT] Supabase delete user info: {e}")

        # 6. Now it is safe to delete the User row (no more Student rows reference it)
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
