import asyncio
from app.db.database import engine
from app.db.models import User, Student
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import uuid

async def main():
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        # Check if student record for Vasanth Raam already exists
        user_id = uuid.UUID("066f3021-e091-4de0-8ce1-f47dd40d4329")
        s_res = await session.execute(select(Student).where(Student.user_id == user_id))
        student = s_res.scalars().first()
        
        if student:
            print(f"Student profile already exists for User ID {user_id}")
            return
            
        print("Inserting missing Student profile for vasanthraam1@gmail.com...")
        new_student = Student(
            id=uuid.uuid4(),
            user_id=user_id,
            parent_id=user_id,
            first_name="Vasanth",
            last_name="Raam",
            date_of_birth=None,
            mother_name=None,
            father_name=None,
            parent_phone_number=None
        )
        session.add(new_student)
        await session.commit()
        print("Successfully created student profile!")

if __name__ == "__main__":
    asyncio.run(main())
