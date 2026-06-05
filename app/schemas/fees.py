from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.schemas.user import UserResponse

class FeeCreate(BaseModel):
    user_id: UUID
    amount: float
    due_date: datetime

class FeeCreateBulk(BaseModel):
    user_ids: List[UUID]
    amount: float
    due_date: datetime
    course_id: Optional[UUID] = None
    batch_id: Optional[UUID] = None

class FeeResponse(BaseModel):
    id: UUID
    user_id: UUID
    amount: float
    status: str
    due_date: Optional[datetime]
    paid_at: Optional[datetime]
    created_at: datetime
    course_id: Optional[UUID] = None
    batch_id: Optional[UUID] = None
    user: Optional[UserResponse] = None

    class Config:
        from_attributes = True

class AdminUPISchema(BaseModel):
    upi_id: str
