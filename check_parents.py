import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import User, Student

async def check_links():
    async with AsyncSessionLocal() as db:
        parents_res = await db.execute(select(User).where(User.role == "parent"))
        parents = parents_res.scalars().all()
        
        if not parents:
            print("No parents found.")
            return

        for p in parents:
            st_res = await db.execute(select(Student).where(Student.parent_id == p.id))
            students = st_res.scalars().all()
            print(f"Parent {p.full_name} ({p.id}) has {len(students)} students.")
            for s in students:
                print(f"  - Student: {s.first_name} {s.last_name}")

if __name__ == "__main__":
    asyncio.run(check_links())
