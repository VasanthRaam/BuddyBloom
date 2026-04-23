import asyncio
import sys
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import Quiz, Course, Student, Enrollment, Batch

async def check_quizzes():
    if sys.stdout.encoding != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
    async with AsyncSessionLocal() as db:
        print("--- Quizzes ---")
        res = await db.execute(select(Quiz))
        quizzes = res.scalars().all()
        print(f"Total Quizzes: {len(quizzes)}")
        for q in quizzes:
            print(f" - {q.title} (ID: {q.id}, Course: {q.course_id}, Creator: {q.created_by})")
            
        print("\n--- Courses ---")
        res = await db.execute(select(Course))
        courses = res.scalars().all()
        for c in courses:
            print(f" - {c.name} (ID: {c.id})")

        print("\n--- Students & Batches ---")
        res = await db.execute(select(Student))
        students = res.scalars().all()
        for s in students:
            print(f" - Student: {s.first_name} {s.last_name}")
            e_res = await db.execute(select(Enrollment).where(Enrollment.student_id == s.id))
            enrollments = e_res.scalars().all()
            for e in enrollments:
                b_res = await db.execute(select(Batch).where(Batch.id == e.batch_id))
                b = b_res.scalars().first()
                print(f"   -> Enrolled in Batch: {b.name} (Course ID: {b.course_id})")

if __name__ == "__main__":
    asyncio.run(check_quizzes())
