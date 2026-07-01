import asyncio
from app.db.database import AsyncSessionLocal
from app.db.models import UserPushToken, User
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

async def check_tokens():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserPushToken)
            .options(selectinload(UserPushToken.user))
        )
        tokens = result.scalars().all()
        
        print(f"\n--- Registered Push Tokens ({len(tokens)}) ---")
        for t in tokens:
            email = t.user.email if t.user else "Unknown"
            print(f"User: {email} | Token: {t.push_token[:30]}... | Device: {t.device_type}")
        print("------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(check_tokens())
