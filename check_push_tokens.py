import asyncio
from app.db.database import AsyncSessionLocal
from app.db.models import UserPushToken, User
from sqlalchemy.future import select

async def check_tokens():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserPushToken).join(User))
        tokens = result.scalars().all()
        
        print(f"\n--- Registered Push Tokens ({len(tokens)}) ---")
        for t in tokens:
            print(f"User: {t.user.email} | Token: {t.push_token[:20]}... | Device: {t.device_type}")
        print("------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(check_tokens())
