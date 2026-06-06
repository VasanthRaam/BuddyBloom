from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional

class PendingEnrollmentCreate(BaseModel):
    student_id: Optional[UUID4] = None
    batch_id: UUID4

class PendingEnrollmentResponse(BaseModel):
    id: UUID4
    student_id: UUID4
    batch_id: UUID4
    status: str
    created_at: datetime
    student_name: Optional[str] = None
    batch_name: Optional[str] = None
    course_name: Optional[str] = None

    class Config:
        from_attributes = True
