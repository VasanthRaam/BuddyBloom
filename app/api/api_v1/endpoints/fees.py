from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Any
from uuid import UUID

from app.db.database import get_db
from app.db.models import User, FeePayment, UserRole, Notification
from app.api.deps import get_current_user
from app.schemas.fees import FeeCreateBulk, FeeResponse, AdminUPISchema

router = APIRouter()

@router.post("/", response_model=List[FeeResponse])
def create_fee_reminder(
    *,
    db: Session = Depends(get_db),
    fee_in: FeeCreateBulk,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Create a new fee reminder for multiple students and send notifications. Admin only.
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    created_fees = []
    
    for uid in fee_in.user_ids:
        student = db.query(User).filter(User.id == uid, User.role == UserRole.student).first()
        if not student:
            continue
            
        fee = FeePayment(
            user_id=uid,
            amount=fee_in.amount,
            due_date=fee_in.due_date,
            status="pending"
        )
        db.add(fee)
        
        notification = Notification(
            user_id=uid,
            title="Fee Reminder",
            message=f"You have a pending fee of ₹{fee_in.amount} due by {fee_in.due_date.strftime('%Y-%m-%d')}.",
            link_to="Fees"
        )
        db.add(notification)
        
        created_fees.append(fee)

    db.commit()
    for fee in created_fees:
        db.refresh(fee)
        
    return created_fees

@router.get("/", response_model=List[FeeResponse])
def get_fees(
    db: Session = Depends(get_db),
    student_id: UUID = None,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get fee payments. Admin can filter by student_id.
    Students can only see their own fees.
    """
    query = db.query(FeePayment)
    
    if current_user.role == UserRole.admin:
        if student_id:
            query = query.filter(FeePayment.user_id == student_id)
    elif current_user.role == UserRole.student:
        query = query.filter(FeePayment.user_id == current_user.id)
    else:
        # parent or teacher shouldn't see this unless requested, for now restrict or let parent see
        if current_user.role == UserRole.parent:
             query = query.join(User).filter(User.id == FeePayment.user_id) # Need logic for parent's students, skipping for simplicity, just return empty
             return []
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return query.all()

@router.put("/{fee_id}/receive", response_model=FeeResponse)
def mark_fee_received(
    *,
    db: Session = Depends(get_db),
    fee_id: UUID,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Mark a fee as paid. Admin only.
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    fee = db.query(FeePayment).filter(FeePayment.id == fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee payment not found")

    fee.status = "paid"
    fee.paid_at = func.now()
    db.add(fee)
    db.commit()
    db.refresh(fee)
    return fee

@router.get("/admin-upi", response_model=AdminUPISchema)
def get_admin_upi(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get the admin's UPI ID.
    If called by an admin, return their own UPI ID if available.
    Otherwise, return the first admin's UPI ID.
    """
    if current_user.role == UserRole.admin:
        return {"upi_id": current_user.upi_id or ""}
        
    admin = db.query(User).filter(User.role == UserRole.admin, User.upi_id != None).first()
    return {"upi_id": admin.upi_id if admin else ""}

@router.put("/admin-upi", response_model=AdminUPISchema)
def update_admin_upi(
    *,
    db: Session = Depends(get_db),
    upi_in: AdminUPISchema,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Update the admin's UPI ID. Admin only.
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    current_user.upi_id = upi_in.upi_id
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return {"upi_id": current_user.upi_id}
