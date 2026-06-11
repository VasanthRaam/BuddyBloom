from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from uuid import UUID
from datetime import date

from app.db.database import get_db
from app.schemas.attendance import AttendanceBulkCreate, AttendanceResponse, HolidayResponse, LeaveRequestCreate, LeaveRequestResponse
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

@router.get("/holidays", response_model=List[HolidayResponse])
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
    from app.db.models import AcademyHoliday, Attendance
    from sqlalchemy import delete
    from app.services.notification_service import NotificationService
    
    # Check if exists
    res = await db.execute(select(AcademyHoliday).where(AcademyHoliday.date == holiday_date))
    if res.scalars().first():
        raise HTTPException(status_code=400, detail="This date is already marked as a holiday.")
        
    db_holiday = AcademyHoliday(
        date=holiday_date,
        description=description,
        created_by=UUID(current_user["id"])
    )
    db.add(db_holiday)
    
    # Delete any existing attendance records for all students on this date
    # so that it does not count towards their attendance rate calculations.
    await db.execute(delete(Attendance).where(Attendance.date == holiday_date))
    
    await db.commit()
    
    # Send push and in-app notifications to all students
    try:
        await NotificationService.notify_all_students_for_holiday(db, holiday_date, description)
    except Exception as e:
        print(f"⚠️ [HOLIDAY] Failed to notify students: {e}")
        
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

@router.post("/leave_requests", response_model=LeaveRequestResponse, status_code=201)
async def create_leave_request(
    request: LeaveRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["student", "parent"]))
):
    """
    Submit a leave request.
    """
    from app.db.models import LeaveRequest, Student, Notification, User
    from uuid import UUID

    # Get student profile
    res = await db.execute(select(Student).where(Student.user_id == UUID(current_user["id"])))
    student = res.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")

    leave_req = LeaveRequest(
        student_id=student.id,
        start_date=request.start_date,
        end_date=request.end_date,
        reason=request.reason,
        status="pending"
    )
    db.add(leave_req)
    
    # Notify Admin and Teachers
    from app.services.notification_service import NotificationService
    admin_res = await db.execute(select(User).where(User.role == "admin"))
    admins = admin_res.scalars().all()
    
    for admin in admins:
        db.add(Notification(
            user_id=admin.id,
            title="New Leave Request",
            message=f"{student.first_name} requested leave from {request.start_date} to {request.end_date}.",
            link_to="PendingApprovals"
        ))
    
    await db.commit()

    # Trigger push notifications for admins
    for admin in admins:
        try:
            await NotificationService.send_push_notification(
                db,
                admin.id,
                "New Leave Request 📅",
                f"{student.first_name} requested leave from {request.start_date} to {request.end_date}.",
                {"type": "leave_request", "action": "approval", "screen": "PendingApprovals"}
            )
        except Exception as e:
            print(f"⚠️ [LEAVE] Failed to send push notification to admin {admin.id}: {e}")
    await db.refresh(leave_req)
    return leave_req

@router.get("/leave_requests", response_model=List[LeaveRequestResponse])
async def get_leave_requests(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["admin", "teacher"]))
):
    """
    Get all pending leave requests for Admins and Teachers.
    """
    from app.db.models import LeaveRequest
    from sqlalchemy.orm import selectinload
    
    # For now, return all pending requests. In a more advanced setup, teachers 
    # would only see requests for students in their batches.
    result = await db.execute(
        select(LeaveRequest)
        .options(selectinload(LeaveRequest.student))
        .where(LeaveRequest.status == "pending")
        .order_by(LeaveRequest.created_at.asc())
    )
    requests = result.scalars().all()
    
    response = []
    for req in requests:
        res = LeaveRequestResponse.model_validate(req)
        res.student_name = f"{req.student.first_name} {req.student.last_name}" if req.student else None
        response.append(res)
        
    return response

@router.post("/leave_requests/{request_id}/approve")
async def approve_leave_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["admin", "teacher"]))
):
    """Approve a leave request and create excused attendance records."""
    from app.db.models import LeaveRequest, Attendance, Notification, Enrollment
    from sqlalchemy.orm import selectinload
    import datetime
    
    result = await db.execute(
        select(LeaveRequest)
        .options(selectinload(LeaveRequest.student))
        .where(LeaveRequest.id == request_id)
    )
    leave_req = result.scalars().first()
    if not leave_req or leave_req.status != "pending":
        raise HTTPException(status_code=404, detail="Pending leave request not found.")
        
    leave_req.status = "approved"
    leave_req.handled_by = UUID(current_user["id"])
    
    # Create excused attendance records for all enrolled batches during this date range
    enr_res = await db.execute(select(Enrollment).where(Enrollment.student_id == leave_req.student_id))
    enrollments = enr_res.scalars().all()
    
    current_date = leave_req.start_date
    delta = datetime.timedelta(days=1)
    
    while current_date <= leave_req.end_date:
        for enr in enrollments:
            # Check if record already exists to prevent duplicate key errors
            att_check = await db.execute(select(Attendance).where(
                Attendance.student_id == leave_req.student_id,
                Attendance.batch_id == enr.batch_id,
                Attendance.date == current_date
            ))
            if not att_check.scalars().first():
                att = Attendance(
                    student_id=leave_req.student_id,
                    batch_id=enr.batch_id,
                    date=current_date,
                    status="excused",
                    remarks="Approved Leave"
                )
                db.add(att)
        current_date += delta
        
    # Notify student/parent
    user_id_to_notify = leave_req.student.user_id or leave_req.student.parent_id
    if user_id_to_notify:
        db.add(Notification(
            user_id=user_id_to_notify,
            title="Leave Approved",
            message=f"Leave request for {leave_req.start_date} to {leave_req.end_date} has been approved.",
            link_to="Attendance"
        ))
        
    await db.commit()

    # Trigger push notification for student/parent
    if user_id_to_notify:
        from app.services.notification_service import NotificationService
        try:
            await NotificationService.send_push_notification(
                db,
                user_id_to_notify,
                "Leave Approved ✅",
                f"Leave request for {leave_req.start_date} to {leave_req.end_date} has been approved.",
                {"type": "leave_approved", "screen": "Attendance"}
            )
        except Exception as e:
            print(f"⚠️ [LEAVE] Failed to send push notification to user {user_id_to_notify}: {e}")
    return {"message": "Leave request approved and attendance marked."}

@router.post("/leave_requests/{request_id}/reject")
async def reject_leave_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["admin", "teacher"]))
):
    """Reject a leave request."""
    from app.db.models import LeaveRequest, Notification
    from sqlalchemy.orm import selectinload
    
    result = await db.execute(
        select(LeaveRequest)
        .options(selectinload(LeaveRequest.student))
        .where(LeaveRequest.id == request_id)
    )
    leave_req = result.scalars().first()
    if not leave_req or leave_req.status != "pending":
        raise HTTPException(status_code=404, detail="Pending leave request not found.")
        
    leave_req.status = "rejected"
    leave_req.handled_by = UUID(current_user["id"])
    
    # Notify student/parent
    user_id_to_notify = leave_req.student.user_id or leave_req.student.parent_id
    if user_id_to_notify:
        db.add(Notification(
            user_id=user_id_to_notify,
            title="Leave Rejected",
            message=f"Leave request for {leave_req.start_date} to {leave_req.end_date} was rejected.",
            link_to="Attendance"
        ))
        
    await db.commit()

    # Trigger push notification for student/parent
    if user_id_to_notify:
        from app.services.notification_service import NotificationService
        try:
            await NotificationService.send_push_notification(
                db,
                user_id_to_notify,
                "Leave Rejected ❌",
                f"Leave request for {leave_req.start_date} to {leave_req.end_date} was rejected.",
                {"type": "leave_rejected", "screen": "Attendance"}
            )
        except Exception as e:
            print(f"⚠️ [LEAVE] Failed to send push notification to user {user_id_to_notify}: {e}")
    return {"message": "Leave request rejected."}
