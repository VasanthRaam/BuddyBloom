from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from uuid import UUID
from app.db.database import get_db
from app.db.models import Notification
from app.api.deps import get_current_user

router = APIRouter()

@router.get("")
@router.get("/", include_in_schema=False)
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    user_uuid = UUID(current_user["id"])
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_uuid)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifications = result.scalars().all()
    
    return [
        {
            "id": str(n.id),
            "title": n.title,
            "message": n.message,
            "link_to": n.link_to,
            "is_read": n.is_read,
            "created_at": n.created_at
        } for n in notifications
    ]

@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        notif_uuid = UUID(notification_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid notification ID")

    result = await db.execute(select(Notification).where(Notification.id == notif_uuid))
    notification = result.scalars().first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    notification.is_read = True
    await db.commit()
    return {"status": "success"}
