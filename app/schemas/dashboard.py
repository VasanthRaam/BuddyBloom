from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class AdminStats(BaseModel):
    total_revenue: float
    pending_fees: float
    total_students: int
    total_teachers: int

class TeacherStats(BaseModel):
    avg_performance: float
    active_batches: int
    pending_homeworks: int

class StudentStats(BaseModel):
    attendance_rate: float
    avg_quiz_score: float
    completed_quizzes: int

class DashboardStatsResponse(BaseModel):
    admin: Optional[AdminStats] = None
    teacher: Optional[TeacherStats] = None
    student: Optional[StudentStats] = None
