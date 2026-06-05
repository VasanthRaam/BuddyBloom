from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Any
from uuid import UUID

from app.db.database import get_db
from app.db.models import User, FeePayment, UserRole, Notification
from app.api.deps import get_current_user
from app.schemas.fees import FeeCreateBulk, FeeResponse, AdminUPISchema

router = APIRouter()

@router.post("/", response_model=List[FeeResponse])
async def create_fee_reminder(
    *,
    db: AsyncSession = Depends(get_db),
    fee_in: FeeCreateBulk,
    current_user: dict = Depends(get_current_user)
) -> Any:
    """
    Create a new fee reminder for multiple students and send notifications. Admin only.
    """
    try:
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Not enough permissions")

        created_fees = []
        
        for uid in fee_in.user_ids:
            # Check if user is a student
            student_res = await db.execute(select(User).where(User.id == uid, User.role == UserRole.student))
            student = student_res.scalars().first()
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

        await db.commit()
        
        # Query created fees back eagerly with selectinload(FeePayment.user)
        # to avoid lazy loading crashes during response serialization
        if created_fees:
            fee_ids = [f.id for f in created_fees]
            result = await db.execute(
                select(FeePayment)
                .where(FeePayment.id.in_(fee_ids))
                .options(selectinload(FeePayment.user))
            )
            return result.scalars().all()
            
        return []
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

@router.get("/", response_model=List[FeeResponse])
async def get_fees(
    db: AsyncSession = Depends(get_db),
    student_id: UUID = None,
    current_user: dict = Depends(get_current_user)
) -> Any:
    """
    Get fee payments. Admin can filter by student_id.
    Students can only see their own fees.
    """
    try:
        role = current_user.get("role")
        user_uuid = UUID(current_user["id"])
        
        if role == "admin":
            query = select(FeePayment).options(selectinload(FeePayment.user))
            if student_id:
                query = query.where(FeePayment.user_id == student_id)
        elif role == "student":
            query = select(FeePayment).options(selectinload(FeePayment.user)).where(FeePayment.user_id == user_uuid)
        else:
            # parent or teacher shouldn't see this unless requested, for now restrict or let parent see
            if role == "parent":
                 # Need logic for parent's students, skipping for simplicity, just return empty
                 return []
            raise HTTPException(status_code=403, detail="Not enough permissions")

        res = await db.execute(query)
        return res.scalars().all()
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

@router.put("/{fee_id}/receive", response_model=FeeResponse)
async def mark_fee_received(
    *,
    db: AsyncSession = Depends(get_db),
    fee_id: UUID,
    current_user: dict = Depends(get_current_user)
) -> Any:
    """
    Mark a fee as paid. Admin only.
    """
    try:
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Not enough permissions")

        fee_res = await db.execute(
            select(FeePayment)
            .where(FeePayment.id == fee_id)
            .options(selectinload(FeePayment.user))
        )
        fee = fee_res.scalars().first()
        if not fee:
            raise HTTPException(status_code=404, detail="Fee payment not found")

        fee.status = "paid"
        fee.paid_at = func.now()
        db.add(fee)
        await db.commit()
        await db.refresh(fee)
        return fee
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

@router.get("/admin-upi", response_model=AdminUPISchema)
async def get_admin_upi(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Any:
    """
    Get the admin's UPI ID.
    If called by an admin, return their own UPI ID if available.
    Otherwise, return the first admin's UPI ID.
    """
    try:
        role = current_user.get("role")
        user_uuid = UUID(current_user["id"])
        
        if role == "admin":
            user_res = await db.execute(select(User).where(User.id == user_uuid))
            admin_user = user_res.scalars().first()
            return {"upi_id": admin_user.upi_id if (admin_user and admin_user.upi_id) else ""}
            
        admin_res = await db.execute(select(User).where(User.role == UserRole.admin, User.upi_id != None))
        admin = admin_res.scalars().first()
        return {"upi_id": admin.upi_id if admin else ""}
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

@router.put("/admin-upi", response_model=AdminUPISchema)
async def update_admin_upi(
    *,
    db: AsyncSession = Depends(get_db),
    upi_in: AdminUPISchema,
    current_user: dict = Depends(get_current_user)
) -> Any:
    """
    Update the admin's UPI ID. Admin only.
    """
    try:
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Not enough permissions")

        user_uuid = UUID(current_user["id"])
        user_res = await db.execute(select(User).where(User.id == user_uuid))
        db_user = user_res.scalars().first()
        
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
            
        db_user.upi_id = upi_in.upi_id
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return {"upi_id": db_user.upi_id}
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
