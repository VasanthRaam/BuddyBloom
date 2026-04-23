import asyncio
import os
import sys
import json

# Add the current directory to sys.path to find 'app'
sys.path.append(os.getcwd())

from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal, engine
from app.db.models import Course, Student

async def setup():
    async with AsyncSessionLocal() as db:
        # Get course ID for Quiz Creation
        course_query = await db.execute(select(Course).limit(1))
        course = course_query.scalars().first()

        if not course:
            print("Creating a sample Course...")
            course = Course(name="Sample Course for Quizzes")
            db.add(course)
            await db.commit()
            await db.refresh(course)
            
        print(f"\n--- USE THIS ID TO CREATE A QUIZ ---")
        print(f"course_id: {course.id}")
        
        create_payload = {
            "title": "React Fundamentals",
            "description": "Test your React knowledge",
            "due_date": "2026-12-31T23:59:59Z",
            "course_id": str(course.id)
        }
        print("\nPayload for POST /api/v1/quizzes/:")
        print(json.dumps(create_payload, indent=2))
        
        # Get student ID just to verify they exist for the submission step
        student_query = await db.execute(select(Student).limit(1))
        student = student_query.scalars().first()
        if student:
            print(f"\nYour test student is ready for submission (ID: {student.id})")
        else:
            print("\nWARNING: No student found. You must create one before submitting quizzes.")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(setup())
