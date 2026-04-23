import asyncio
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import Student, Enrollment, Batch, User

async def check_data():
    async with AsyncSessionLocal() as db:
        students = (await db.execute(select(Student))).scalars().all()
        batches = (await db.execute(select(Batch))).scalars().all()
        enrollments = (await db.execute(select(Enrollment))).scalars().all()
        users = (await db.execute(select(User))).scalars().all()
        
        print(f"Users: {len(users)}")
        for u in users:
            print(f" - {u.email} ({u.role})")
            
        print(f"\nStudents: {len(students)}")
        for s in students:
            print(f" - {s.first_name} {s.last_name} (ID: {s.id})")
            
        print(f"\nBatches: {len(batches)}")
        for b in batches:
            print(f" - {b.name} (ID: {b.id}, Teacher: {b.teacher_id})")
            
        print(f"\nEnrollments: {len(enrollments)}")
        for e in enrollments:
            print(f" - Student {e.student_id} -> Batch {e.batch_id}")

if __name__ == "__main__":
    asyncio.run(check_data())
