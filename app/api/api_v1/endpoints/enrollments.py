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
    Student or Parent requests enrollment in a new batch.
    """
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
            
    # Check if already enrolled
    enr_res = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == request.student_id,
            Enrollment.batch_id == request.batch_id
        )
    )
    if enr_res.scalars().first():
        raise HTTPException(status_code=400, detail="Student is already enrolled in this batch.")
        
    # Check if already pending
    pend_res = await db.execute(
        select(PendingEnrollment).where(
            PendingEnrollment.student_id == request.student_id,
            PendingEnrollment.batch_id == request.batch_id,
            PendingEnrollment.status == "pending"
        )
    )
    if pend_res.scalars().first():
        raise HTTPException(status_code=400, detail="An enrollment request for this batch is already pending.")

    pending_enrollment = PendingEnrollment(
        student_id=request.student_id,
        batch_id=request.batch_id,
        status="pending"
    )
    db.add(pending_enrollment)
    
    # Notify Admin
    from app.db.models import User
    admin_res = await db.execute(select(User).where(User.role == UserRole.admin))
    admins = admin_res.scalars().all()
    for admin in admins:
        notif = Notification(
            user_id=admin.id,
            title="New Enrollment Request",
            message=f"{student.first_name} {student.last_name} requested to join a new course.",
            link_to="PendingApprovals"
        )
        db.add(notif)
        
    await db.commit()
    await db.refresh(pending_enrollment)
    
    return PendingEnrollmentResponse(
        id=pending_enrollment.id,
        student_id=pending_enrollment.student_id,
        batch_id=pending_enrollment.batch_id,
        status=pending_enrollment.status,
        created_at=pending_enrollment.created_at
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
    return {"message": "Enrollment rejected."}
