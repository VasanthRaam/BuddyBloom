import asyncio
import os
import sys

# Add the current directory to sys.path to find 'app'
sys.path.append(os.getcwd())

from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal, engine
from app.db.models import Batch, Student, User, Course

async def setup():
    async with AsyncSessionLocal() as db:
        # 1. Create a Sample Course if none exists
        course_query = await db.execute(select(Course).limit(1))
        course = course_query.scalars().first()
        
        if not course:
            print("Creating a new Sample Course...")
            course = Course(name="Yoga for Beginners", description="Introductory yoga class")
            db.add(course)
            await db.commit()
            await db.refresh(course)
        else:
            print(f"Found existing Course: {course.name}")

        # 2. Create a Sample Batch if none exists
        batch_query = await db.execute(select(Batch).limit(1))
        batch = batch_query.scalars().first()
        
        if not batch:
            print("Creating a new Sample Batch...")
            batch = Batch(name="Morning Yoga Batch", course_id=course.id)
            db.add(batch)
            await db.commit()
            await db.refresh(batch)
        else:
            print(f"Found existing Batch: {batch.name}")

        # 3. Find the student
        student_query = await db.execute(select(Student))
        student = student_query.scalars().first()
        
        if not student:
            print("No student profile found in 'students' table.")
            user_query = await db.execute(select(User).where(User.role == 'student'))
            user = user_query.scalars().first()
            
            if user:
                print(f"Creating student profile for user: {user.full_name}")
                student = Student(
                    id=user.id,
                    user_id=user.id,
                    parent_id=user.id, # Mocking parent as self
                    first_name=user.full_name.split()[0],
                    last_name=user.full_name.split()[-1] if ' ' in user.full_name else "Student"
                )
                db.add(student)
                await db.commit()
                await db.refresh(student)
            else:
                print("Error: No user with role 'student' found. Please create a user first.")
                return

        print(f"\n--- SUCCESS ---")
        print(f"Course ID: {course.id}")
        print(f"Batch ID: {batch.id}")
        print(f"Student ID: {student.id}")
        print(f"\n--- COPY THIS JSON INTO POST /api/v1/attendance/bulk ---")
        import json
        payload = {
            "batch_id": str(batch.id),
            "date": "2026-04-21",
            "records": [
                {
                    "student_id": str(student.id),
                    "status": "present",
                    "remarks": "Testing attendance!"
                }
            ]
        }
        print(json.dumps(payload, indent=2))
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(setup())
