import asyncio
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import User

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == 'teacher1@buddybloom.com'))
        user = res.scalars().first()
        if user:
            print(f"User found: {user.full_name} (ID: {user.id})")
        else:
            print("User NOT found")

if __name__ == "__main__":
    asyncio.run(check())
