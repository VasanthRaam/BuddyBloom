from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List
from uuid import UUID
from app.db.models import User
from app.schemas.user import UserCreate

class UserService:
    @staticmethod
    async def get_user(db: AsyncSession, user_id: UUID) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    @staticmethod
    async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
        db_user = User(**user_in.model_dump())
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        
        # Notify Admins about the new registration
        try:
            from app.services.notification_service import NotificationService
            await NotificationService.notify_admins_new_registration(
                db, 
                db_user.full_name, 
                db_user.role.value if hasattr(db_user.role, 'value') else str(db_user.role)
            )
        except Exception as e:
            print(f"⚠️ Failed to notify admins about new registration: {e}")
            
        return db_user

    @staticmethod
    async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
        result = await db.execute(select(User).offset(skip).limit(limit))
        return list(result.scalars().all())
