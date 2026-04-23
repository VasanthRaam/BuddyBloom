import asyncio
import uuid
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal, engine, Base
from app.db.models import Course, Batch, User, Student, Enrollment, Attendance, ProgressTracking, Homework, HomeworkSubmission

async def seed_data():
    print("Starting Seeding: Courses and Batches...")
    
    async with AsyncSessionLocal() as db:
        # 1. Clear old data (respecting foreign keys)
        print("Clearing old data...")
        await db.execute(Attendance.__table__.delete())
        await db.execute(HomeworkSubmission.__table__.delete())
        await db.execute(Homework.__table__.delete())
        await db.execute(Enrollment.__table__.delete())
        await db.execute(ProgressTracking.__table__.delete())
        await db.execute(Batch.__table__.delete())
        await db.execute(Course.__table__.delete())
        await db.commit()
        
        # 2. Define Courses
        courses_data = ["Hindi", "Subject", "Dance", "Keyboard"]
        batches_names = ["Trichy batch", "Vaiyampatti batch"]
        
        created_courses = []
        for name in courses_data:
            course = Course(
                id=uuid.uuid4(),
                name=name,
                description=f"Standard {name} course"
            )
            db.add(course)
            created_courses.append(course)
        
        await db.flush() # Ensure courses have IDs
        
        # 3. Create Batches for each Course
        for course in created_courses:
            for b_name in batches_names:
                batch = Batch(
                    id=uuid.uuid4(),
                    course_id=course.id,
                    name=b_name
                )
                db.add(batch)
        
        await db.commit()
        print(f"Successfully created {len(courses_data)} courses with {len(batches_names)} batches each.")

if __name__ == "__main__":
    asyncio.run(seed_data())
