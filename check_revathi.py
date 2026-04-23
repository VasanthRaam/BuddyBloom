import asyncio
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import User

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == 'revathi@gmail.com'))
        user = res.scalars().first()
        if user:
            print(f"User revathi@gmail.com found: {user.full_name}")
        else:
            print("User revathi@gmail.com NOT found")

if __name__ == "__main__":
    asyncio.run(check())
