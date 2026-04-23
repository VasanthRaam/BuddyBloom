from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.db.models import UserRole

class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    role: UserRole
    phone: Optional[str] = None

class UserCreate(UserBase):
    id: UUID  # This will be the ID from Supabase Auth

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None

class UserResponse(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
