import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List

from app.db.database import get_db
from app.db.models import PendingEnrollment, Enrollment, Student, Batch, Notification, UserRole
from app.api.deps import get_current_user
from app.schemas.enrollment import PendingEnrollmentCreate, PendingEnrollmentResponse

router = APIRouter()

@router.post("/request", response_model=PendingEnrollmentResponse)
async def request_enrollment(
    request: PendingEnrollmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Student or Parent requests enrollment in one or multiple batches/courses.
    """
    from sqlalchemy import cast, String, func
    from app.db.models import User
    from app.services.notification_service import NotificationService

    user_uuid = uuid.UUID(current_user["id"])
    
    # Auto-infer student_id if missing and user is a student
    if not request.student_id:
        if current_user["role"] == "student":
            st_res = await db.execute(select(Student).where(Student.user_id == user_uuid))
            st = st_res.scalars().first()
            if not st:
                raise HTTPException(status_code=404, detail="Student profile not found for user.")
            request.student_id = st.id
        else:
            raise HTTPException(status_code=400, detail="student_id is required.")

    # Verify student exists and belongs to user (or user is admin)
    student_res = await db.execute(select(Student).where(Student.id == request.student_id))
    student = student_res.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
        
    if current_user["role"] not in ["admin"]:
        if student.user_id != user_uuid and student.parent_id != user_uuid:
            raise HTTPException(status_code=403, detail="Not authorized to enroll this student.")

    # Collect batch IDs (from batch_ids list or single batch_id)
    target_batch_ids = []
    if request.batch_ids:
        target_batch_ids.extend(request.batch_ids)
    if request.batch_id and request.batch_id not in target_batch_ids:
        target_batch_ids.append(request.batch_id)

    if not target_batch_ids:
        raise HTTPException(status_code=400, detail="At least one batch_id must be provided.")

    created_pendings = []
    requested_course_names = []

    for b_id in target_batch_ids:
        # Check if already enrolled
        enr_res = await db.execute(
            select(Enrollment).where(
                Enrollment.student_id == request.student_id,
                Enrollment.batch_id == b_id
            )
        )
        if enr_res.scalars().first():
            continue  # Skip if already enrolled
            
        # Check if already pending
        pend_res = await db.execute(
            select(PendingEnrollment).where(
                PendingEnrollment.student_id == request.student_id,
                PendingEnrollment.batch_id == b_id,
                PendingEnrollment.status == "pending"
            )
        )
        if pend_res.scalars().first():
            continue  # Skip if already pending

        pending_enrollment = PendingEnrollment(
            student_id=request.student_id,
            batch_id=b_id,
            status="pending"
        )
        db.add(pending_enrollment)
        created_pendings.append(pending_enrollment)

        # Get course name for notification
        b_res = await db.execute(
            select(Batch, Course).join(Course, Batch.course_id == Course.id).where(Batch.id == b_id)
        )
        b_row = b_res.first()
        if b_row and b_row[1]:
            requested_course_names.append(b_row[1].name)

    if not created_pendings:
        raise HTTPException(status_code=400, detail="Student is already enrolled or has pending requests for the selected batch(es).")

    # Notify Admins
    admin_res = await db.execute(
        select(User).where(
            (User.role == UserRole.admin) |
            (cast(User.role, String) == 'admin') |
            (func.lower(cast(User.role, String)) == 'admin')
        )
    )
    admins = admin_res.scalars().all()
    courses_str = ", ".join(set(requested_course_names)) if requested_course_names else "new courses"
    student_name = f"{student.first_name} {student.last_name}".strip()

    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            title="New Enrollment Request 📝",
            message=f"{student_name} requested enrollment in: {courses_str}",
            link_to="PendingApprovals"
        )
        db.add(notif)

    # Notify Student/Parent in DB
    student_user_id = student.user_id or student.parent_id
    if student_user_id:
        st_notif = Notification(
            user_id=student_user_id,
            title="Enrollment Request Sent ⏳",
            message=f"Your request to enroll in {courses_str} has been sent to Admin for approval.",
            link_to="MyCourses"
        )
        db.add(st_notif)
        
    await db.commit()

    for p in created_pendings:
        await db.refresh(p)
    
    # Trigger push notifications for admins
    for admin in admins:
        try:
            await NotificationService.send_push_notification(
                db,
                admin.id,
                "New Enrollment Request 📝",
                f"{student_name} requested enrollment in: {courses_str}",
                {"type": "enrollment_request", "action": "approval", "screen": "PendingApprovals"}
            )
        except Exception as e:
            print(f"⚠️ [ENROLLMENT] Failed to send push notification to admin {admin.id}: {e}")

    # Return primary created pending enrollment
    first_p = created_pendings[0]
    return PendingEnrollmentResponse(
        id=first_p.id,
        student_id=first_p.student_id,
        batch_id=first_p.batch_id,
        status=first_p.status,
        created_at=first_p.created_at
    )

@router.get("/pending", response_model=List[PendingEnrollmentResponse])
async def get_pending_enrollments(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all pending enrollments (Admin only).
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view pending enrollments.")
        
    result = await db.execute(
        select(PendingEnrollment)
        .options(
            selectinload(PendingEnrollment.student),
            selectinload(PendingEnrollment.batch).selectinload(Batch.course)
        )
        .where(PendingEnrollment.status == "pending")
        .order_by(PendingEnrollment.created_at.asc())
    )
    pendings = result.scalars().all()
    
    response = []
    for p in pendings:
        response.append(PendingEnrollmentResponse(
            id=p.id,
            student_id=p.student_id,
            batch_id=p.batch_id,
            status=p.status,
            created_at=p.created_at,
            student_name=f"{p.student.first_name} {p.student.last_name}" if p.student else None,
            batch_name=p.batch.name if p.batch else None,
            course_name=p.batch.course.name if p.batch and p.batch.course else None
        ))
    return response

@router.post("/{enrollment_id}/approve")
async def approve_enrollment(
    enrollment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Admin approves a pending enrollment.
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can approve enrollments.")
        
    result = await db.execute(
        select(PendingEnrollment)
        .options(selectinload(PendingEnrollment.student), selectinload(PendingEnrollment.batch).selectinload(Batch.course))
        .where(PendingEnrollment.id == enrollment_id)
    )
    pending = result.scalars().first()
    if not pending or pending.status != "pending":
        raise HTTPException(status_code=404, detail="Pending enrollment not found.")
        
    # Create the actual enrollment
    enrollment = Enrollment(
        student_id=pending.student_id,
        batch_id=pending.batch_id
    )
    db.add(enrollment)
    
    pending.status = "approved"
    
    # Notify parent/student
    user_id_to_notify = pending.student.user_id or pending.student.parent_id
    course_name = pending.batch.course.name if pending.batch and pending.batch.course else "a course"
    if user_id_to_notify:
        notif = Notification(
            user_id=user_id_to_notify,
            title="Enrollment Approved",
            message=f"Your request to join {course_name} has been approved!",
            link_to="MyCourses"
        )
        db.add(notif)
        
    await db.commit()

    # Trigger push notification for student/parent
    if user_id_to_notify:
        from app.services.notification_service import NotificationService
        try:
            await NotificationService.send_push_notification(
                db,
                user_id_to_notify,
                "Enrollment Approved 🎉",
                f"Your request to join {course_name} has been approved!",
                {"type": "enrollment_approved", "screen": "MyCourses"}
            )
        except Exception as e:
            print(f"⚠️ [ENROLLMENT] Failed to send push notification to user {user_id_to_notify}: {e}")
    return {"message": "Enrollment approved."}

@router.post("/{enrollment_id}/reject")
async def reject_enrollment(
    enrollment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Admin rejects a pending enrollment.
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can reject enrollments.")
        
    result = await db.execute(
        select(PendingEnrollment)
        .options(selectinload(PendingEnrollment.student), selectinload(PendingEnrollment.batch).selectinload(Batch.course))
        .where(PendingEnrollment.id == enrollment_id)
    )
    pending = result.scalars().first()
    if not pending or pending.status != "pending":
        raise HTTPException(status_code=404, detail="Pending enrollment not found.")
        
    pending.status = "rejected"
    
    # Notify parent/student
    user_id_to_notify = pending.student.user_id or pending.student.parent_id
    course_name = pending.batch.course.name if pending.batch and pending.batch.course else "a course"
    if user_id_to_notify:
        notif = Notification(
            user_id=user_id_to_notify,
            title="Enrollment Rejected",
            message=f"Your request to join {course_name} was rejected.",
            link_to="MyCourses"
        )
        db.add(notif)
        
    await db.commit()

    # Trigger push notification for student/parent
    if user_id_to_notify:
        from app.services.notification_service import NotificationService
        try:
            await NotificationService.send_push_notification(
                db,
                user_id_to_notify,
                "Enrollment Rejected ❌",
                f"Your request to join {course_name} was rejected.",
                {"type": "enrollment_rejected", "screen": "MyCourses"}
            )
        except Exception as e:
            print(f"⚠️ [ENROLLMENT] Failed to send push notification to user {user_id_to_notify}: {e}")
    return {"message": "Enrollment rejected."}
