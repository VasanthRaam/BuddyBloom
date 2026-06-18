import asyncio
from app.db.database import AsyncSessionLocal
from app.db.models import User
from sqlalchemy.future import select

async def run():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User))
        for u in res.scalars().all():
            print(f"Email: {u.email}, Phone: {u.phone}, Role: {u.role}, Approved: {u.is_approved}")

if __name__ == "__main__":
    asyncio.run(run())
