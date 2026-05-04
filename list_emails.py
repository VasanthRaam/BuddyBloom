import asyncio
from app.db.database import AsyncSessionLocal
from app.db.models import User
from sqlalchemy.future import select

async def list_users():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User.email, User.full_name))
        for email, name in result.all():
            print(f"{email} ({name})")

if __name__ == "__main__":
    asyncio.run(list_users())
