import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import Attendance, Student

async def check_attendance():
    async with AsyncSessionLocal() as db:
        att_res = await db.execute(select(Attendance))
        records = att_res.scalars().all()
        print(f"Total attendance records: {len(records)}")
        for r in records:
            st_res = await db.execute(select(Student).where(Student.id == r.student_id))
            st = st_res.scalars().first()
            print(f"Record for {st.first_name if st else 'Unknown'} on {r.date}: {r.status}")

if __name__ == "__main__":
    asyncio.run(check_attendance())
