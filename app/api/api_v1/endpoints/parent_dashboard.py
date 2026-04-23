from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.db.database import get_db
from app.schemas.parent_dashboard import (
    StudentSummary, AttendanceSummary, ProgressSummary, QuizResultSummary
)
from app.services.parent_dashboard_service import ParentDashboardService
from app.api.deps import RequireRole

router = APIRouter()

async def verify_parent_child(student_id: UUID, db: AsyncSession, current_user: dict):
    """Dependency-like function to enforce security check."""
    is_authorized = await ParentDashboardService.verify_parent_access(db, UUID(current_user["id"]), student_id)
    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this student's data."
        )

@router.get("/students", response_model=List[StudentSummary])
async def get_my_students(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["parent"]))
):
    """
    Get a list of all students linked to the current parent.
    """
    students = await ParentDashboardService.get_students(db, UUID(current_user["id"]))
    return students

@router.get("/{student_id}/attendance", response_model=AttendanceSummary)
async def get_attendance(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["parent"]))
):
    """
    Get aggregated attendance summary for a specific student.
    """
    await verify_parent_child(student_id, db, current_user)
    return await ParentDashboardService.get_attendance_summary(db, student_id)

@router.get("/{student_id}/progress", response_model=List[ProgressSummary])
async def get_progress(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["parent"]))
):
    """
    Get progress tracking milestones for a specific student.
    """
    await verify_parent_child(student_id, db, current_user)
    return await ParentDashboardService.get_progress_summary(db, student_id)

@router.get("/{student_id}/quizzes", response_model=List[QuizResultSummary])
async def get_quizzes(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(RequireRole(["parent"]))
):
    """
    Get quiz results and scores for a specific student.
    """
    await verify_parent_child(student_id, db, current_user)
    return await ParentDashboardService.get_quiz_results(db, student_id)
