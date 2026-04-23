from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from app.db.models import AttendanceStatus

class AttendanceBase(BaseModel):
    student_id: UUID
    status: AttendanceStatus
    remarks: Optional[str] = None

class AttendanceBulkCreate(BaseModel):
    batch_id: UUID
    date: date
    records: List[AttendanceBase]

class AttendanceResponse(AttendanceBase):
    id: UUID
    batch_id: UUID
    date: date
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
