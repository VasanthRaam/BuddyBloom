from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.db.database import get_db
from app.schemas.homework import HomeworkCreate, HomeworkResponse
from app.services.homework_service import HomeworkService
from app.api.deps import RequireRole

router = APIRouter()

@router.post("", response_model=HomeworkResponse)
async def create_homework(
    hw_in: HomeworkCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["teacher", "admin"]))
):
    """
    Create a new homework assignment and notify students.
    """
    hw = await HomeworkService.create_homework(db, UUID(current_user["id"]), hw_in)
    
    async def notify_students(batch_id_str, homework_id_str, title, description):
        from app.db.database import AsyncSessionLocal
        from app.services.notification_service import NotificationService
        async with AsyncSessionLocal() as session:
            await NotificationService.notify_students_for_homework(
                session, UUID(batch_id_str), UUID(homework_id_str), title, description
            )
            
    background_tasks.add_task(notify_students, str(hw.batch_id), str(hw.id), hw.title, hw.description)
    return hw

@router.get("", response_model=List[HomeworkResponse])
async def get_my_homework(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["teacher", "admin", "student", "parent"]))
):
    """
    Get all homework assignments relevant to the current user.
    """
    return await HomeworkService.get_user_homeworks(db, UUID(current_user["id"]), current_user["role"])

@router.post("/{homework_id}/toggle-complete")
async def toggle_homework_complete(
    homework_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["student"]))
):
    """
    Mark a homework as completed or incomplete for the current student.
    """
    success = await HomeworkService.toggle_homework_complete(db, homework_id, UUID(current_user["id"]))
    return {"success": success}

@router.get("/batch/{batch_id}", response_model=List[HomeworkResponse])
async def get_batch_homeworks(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["teacher", "admin", "student", "parent"]))
):
    """
    Get all homework assignments for a specific batch.
    """
    return await HomeworkService.get_batch_homeworks(db, batch_id)
