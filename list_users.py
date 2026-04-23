import asyncio
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import User

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User))
        users = res.scalars().all()
        print(f"Total users in DB: {len(users)}")
        for u in users:
            print(f"- {u.email} ({u.role}) ID: {u.id}")

if __name__ == "__main__":
    asyncio.run(check())
