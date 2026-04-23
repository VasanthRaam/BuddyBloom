from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime, date

class StudentSummary(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    date_of_birth: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)

class AttendanceRecord(BaseModel):
    date: date
    status: str

class AttendanceSummary(BaseModel):
    student_id: UUID
    total_present: int
    total_absent: int
    total_late: int
    total_excused: int
    attendance_percentage: float
    records: List[AttendanceRecord] = []

class ProgressSummary(BaseModel):
    id: UUID
    course_name: str
    milestone_name: str
    evaluation_score: Optional[int] = None
    remarks: Optional[str] = None
    recorded_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)

class QuizResultSummary(BaseModel):
    attempt_id: UUID
    quiz_title: str
    course_name: str
    total_score: int
    max_score: int
    attempted_at: datetime
    percentage: float

    model_config = ConfigDict(from_attributes=True)
