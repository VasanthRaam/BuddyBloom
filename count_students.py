import asyncio
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import Student

async def get_count():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Student))
        students = res.scalars().all()
        print('Student count:', len(students))
        for s in students:
            print(f"Student: {s.first_name} {s.last_name}")

if __name__ == "__main__":
    asyncio.run(get_count())
