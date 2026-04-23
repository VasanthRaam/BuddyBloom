from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class HomeworkCreate(BaseModel):
    batch_id: UUID
    student_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None

class HomeworkResponse(BaseModel):
    id: UUID
    batch_id: UUID
    student_id: Optional[UUID] = None
    teacher_id: UUID
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    created_at: datetime
    is_completed: bool = False

    class Config:
        from_attributes = True
