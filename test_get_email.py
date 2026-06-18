import asyncio
from app.db.database import AsyncSessionLocal
from app.db.models import User
from sqlalchemy import select

async def get_email():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User.email).limit(1))
        emails = res.scalars().all()
        print("Test Email:", emails[0] if emails else "No user found")

if __name__ == "__main__":
    asyncio.run(get_email())
