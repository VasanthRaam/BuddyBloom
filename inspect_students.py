import asyncio
from app.db.database import engine
from app.db.models import User, Student
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

async def main():
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        # Users
        u_res = await session.execute(select(User).where(User.role == "student"))
        users = u_res.scalars().all()
        print("Users with role 'student':")
        for u in users:
            print(f"- ID: {u.id}, Email: {u.email}, Name: {u.full_name}, Approved: {u.is_approved}")
            
        # Students
        s_res = await session.execute(select(Student))
        students = s_res.scalars().all()
        print("\nStudent Profiles in database:")
        for s in students:
            print(f"- ID: {s.id}, UserID: {s.user_id}, Name: {s.first_name} {s.last_name}")

if __name__ == "__main__":
    asyncio.run(main())
