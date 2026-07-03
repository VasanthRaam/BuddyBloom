from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


# ── Profile Schemas ─────────────────────────────────────────────────────────

class ProfileUpdateRequest(BaseModel):
    """Only these fields are editable by the user themselves."""
    phone: Optional[str] = None
    email: Optional[str] = None
    profile_picture: Optional[str] = None  # Supabase Storage public URL


class ProfilePhotoUploadResponse(BaseModel):
    upload_url: str
    public_url: str
    path: str


class EnrollmentInfo(BaseModel):
    batch_id: str
    batch_name: str
    course_id: str
    course_name: str

    class Config:
        from_attributes = True


class StudentProfileResponse(BaseModel):
    id: str
    full_name: str
    email: str
    phone: Optional[str]
    profile_picture: Optional[str]
    dob: Optional[str]
    education_qualification: Optional[str]
    # Student-specific (from students table)
    mother_name: Optional[str]
    father_name: Optional[str]
    parent_phone_number: Optional[str]
    # Enrollments
    enrollments: List[EnrollmentInfo] = []
    # StarSpark summary
    current_points: int = 0
    lifetime_points: int = 0
    quiz_points: int = 0
    teacher_bonus_points: int = 0
    rank: Optional[int] = None
    level: int = 1
    level_label: str = "Beginner"
    next_level_points: int = 500


class TeacherProfileResponse(BaseModel):
    id: str
    full_name: str
    email: str
    phone: Optional[str]
    profile_picture: Optional[str]
    assigned_batches: List[EnrollmentInfo] = []
    # Wallet
    wallet_total: int = 1000
    wallet_remaining: int = 1000
    wallet_distributed: int = 0
    wallet_month: Optional[str]
    wallet_expires_at: Optional[str]
    wallet_last_reset: Optional[str]


# ── Points & Rewards Schemas ────────────────────────────────────────────────

class PointTransactionOut(BaseModel):
    id: str
    points: int
    source: str
    reason: Optional[str]
    created_at: str
    given_by_name: Optional[str]

    class Config:
        from_attributes = True


class PointsSummaryResponse(BaseModel):
    student_id: str
    student_name: str
    current_points: int
    lifetime_points: int
    quiz_points: int
    teacher_bonus_points: int
    rank: Optional[int]
    level: int
    level_label: str
    next_level_points: int
    progress_pct: float  # 0.0 to 1.0


class LeaderboardEntry(BaseModel):
    rank: int
    student_id: str
    student_name: str
    profile_picture: Optional[str]
    course_name: Optional[str]
    batch_name: Optional[str]
    current_points: int


class LeaderboardResponse(BaseModel):
    entries: List[LeaderboardEntry]
    total: int
    page: int
    page_size: int


class TeacherGivePointsRequest(BaseModel):
    student_id: str  # students.id (not users.id)
    points: int
    reason: str


class RewardCatalogOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    points_required: int
    image_url: Optional[str]
    is_active: bool
    sort_order: int

    class Config:
        from_attributes = True


class RedeemRequest(BaseModel):
    reward_id: str


class RewardRedemptionOut(BaseModel):
    id: str
    reward_title: str
    points_spent: int
    status: str
    redeemed_at: str

    class Config:
        from_attributes = True
