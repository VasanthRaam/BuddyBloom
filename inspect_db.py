import asyncio
from app.db.database import AsyncSessionLocal
from app.db.models import User, Student, PendingRegistration
from sqlalchemy.future import select

async def main():
    async with AsyncSessionLocal() as session:
        print("--- PENDING REGISTRATIONS ---")
        res = await session.execute(select(PendingRegistration))
        pending = res.scalars().all()
        for p in pending:
            print(f"ID: {p.id}, Email: {p.email}, Status: {p.status}, Role: {p.role}, Mother: {p.mother_name}, Father: {p.father_name}, ParentPhone: {p.parent_phone_number}, DOB: {p.dob}")
            
        print("\n--- USERS ---")
        res = await session.execute(select(User))
        users = res.scalars().all()
        for u in users:
            print(f"ID: {u.id}, Email: {u.email}, Role: {u.role}, Approved: {u.is_approved}")

        print("\n--- STUDENTS ---")
        res = await session.execute(select(Student))
        students = res.scalars().all()
        for s in students:
            print(f"ID: {s.id}, UserID: {s.user_id}, Name: {s.first_name} {s.last_name}, Mother: {s.mother_name}, Father: {s.father_name}, ParentPhone: {s.parent_phone_number}, DOB: {s.date_of_birth}")

if __name__ == "__main__":
    asyncio.run(main())
