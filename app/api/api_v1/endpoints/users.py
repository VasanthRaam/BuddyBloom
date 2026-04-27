from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID
from app.db.database import get_db
from app.schemas.user import UserResponse, UserCreate
from app.services.user_service import UserService

router = APIRouter()

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate, 
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new user in the database.
    This is typically called after a user signs up via Supabase Auth.
    """
    # Check if user already exists
    existing_user = await UserService.get_user(db, user_in.id)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this ID already exists"
        )
    
    return await UserService.create_user(db=db, user_in=user_in)

@router.get("/", response_model=List[UserResponse])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve all users.
    """
    return await UserService.get_users(db, skip=skip, limit=limit)

@router.get("/{user_id}", response_model=UserResponse)
async def read_user(
    user_id: UUID, 
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific user by ID.
    """
    user = await UserService.get_user(db, user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

from app.schemas.user import PushTokenCreate
from app.api.deps import get_current_user
from app.db.models import UserPushToken

@router.post("/push-token", status_code=status.HTTP_200_OK)
async def register_push_token(
    token_in: PushTokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Register an Expo Push Token for the current user.
    """
    user_id = current_user["id"]
    
    # Check if token already exists for this user to avoid duplicates
    result = await db.execute(
        select(UserPushToken).where(
            UserPushToken.user_id == user_id,
            UserPushToken.push_token == token_in.push_token
        )
    )
    existing = result.scalars().first()
    
    if existing:
        return {"status": "already_registered"}
    
    # Create new push token entry
    new_token = UserPushToken(
        user_id=user_id,
        push_token=token_in.push_token,
        device_type=token_in.device_type
    )
    db.add(new_token)
    await db.commit()
    
    return {"status": "registered"}
