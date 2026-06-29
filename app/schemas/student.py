from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import date, datetime
from uuid import UUID

class StudentBase(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: Optional[date] = None

class StudentCreate(StudentBase):
    parent_id: UUID
    user_id: Optional[UUID] = None

class StudentUpdate(StudentBase):
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class StudentResponse(StudentBase):
    id: UUID
    parent_id: UUID
    user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    email: Optional[str] = None
    phone: Optional[str] = None
    courses: list[str] = []
    
    mother_name: Optional[str] = None
    father_name: Optional[str] = None
    parent_phone_number: Optional[str] = None
    education_qualification: Optional[str] = None
    profile_picture: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
