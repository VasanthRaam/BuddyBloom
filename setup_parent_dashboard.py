import asyncio
import os
import sys

# Add the current directory to sys.path to find 'app'
sys.path.append(os.getcwd())

from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal, engine
from app.db.models import Student, Course, ProgressTracking

async def setup():
    async with AsyncSessionLocal() as db:
        # Get a student and course
        student_query = await db.execute(select(Student).limit(1))
        student = student_query.scalars().first()
        
        course_query = await db.execute(select(Course).limit(1))
        course = course_query.scalars().first()
        
        if not student or not course:
            print("Missing student or course to add progress data.")
            return

        # Check if progress exists
        prog_query = await db.execute(select(ProgressTracking).where(ProgressTracking.student_id == student.id))
        existing_prog = prog_query.scalars().first()

        if not existing_prog:
            print(f"Adding sample progress for student {student.first_name}")
            prog1 = ProgressTracking(
                student_id=student.id,
                course_id=course.id,
                milestone_name="Mid-term Exam",
                evaluation_score=85,
                remarks="Excellent improvement!"
            )
            prog2 = ProgressTracking(
                student_id=student.id,
                course_id=course.id,
                milestone_name="Final Project",
                evaluation_score=92,
                remarks="Great presentation skills."
            )
            db.add_all([prog1, prog2])
            await db.commit()
            print("Progress data added successfully.")
        else:
            print("Progress data already exists.")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(setup())
