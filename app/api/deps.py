from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import verify_token
from app.db.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

security = HTTPBearer()

from fastapi import Request

from app.db.models import User
from sqlalchemy.future import select

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db), _ = Depends(security)):
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Fetch the user from the database to get their actual application role
    user_id = request.state.user.get("id")
    email = request.state.user.get("email")
    
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalars().first()
    
    # Fallback to email lookup if ID mismatch
    if not db_user and email:
        result = await db.execute(select(User).where(User.email == email))
        db_user = result.scalars().first()
    
    if not db_user:
        raise HTTPException(status_code=404, detail=f"User profile for {email} not found in database")
        
    return {
        "id": str(db_user.id),
        "role": str(db_user.role.value) if hasattr(db_user.role, 'value') else str(db_user.role),
        "email": db_user.email,
        "full_name": db_user.full_name
    }

class RequireRole:
    def __init__(self, roles: list[str]):
        self.roles = roles

    def __call__(self, user: dict = Depends(get_current_user)):
        if user.get("role") not in self.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return user
