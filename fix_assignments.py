import asyncio
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import Student, Enrollment, Batch, User, UserRole

async def fix_data():
    async with AsyncSessionLocal() as db:
        # 1. Get a teacher
        res = await db.execute(select(User).where(User.role == UserRole.teacher))
        teacher = res.scalars().first()
        
        # 2. Get an admin (can also be a teacher in this context)
        res = await db.execute(select(User).where(User.role == UserRole.admin))
        admin = res.scalars().first()
        
        # 3. Get all batches
        res = await db.execute(select(Batch))
        batches = res.scalars().all()
        
        # 4. Get all students
        res = await db.execute(select(Student))
        students = res.scalars().all()
        
        if not batches:
            print("No batches found to assign.")
            return

        print(f"Assigning teacher {teacher.email if teacher else 'None'} to batches...")
        for b in batches:
            if teacher:
                b.teacher_id = teacher.id
            elif admin:
                b.teacher_id = admin.id
            
            # Enroll all students in every batch for this demo
            for s in students:
                # Check if already enrolled
                e_res = await db.execute(select(Enrollment).where(Enrollment.student_id == s.id, Enrollment.batch_id == b.id))
                if not e_res.scalars().first():
                    db.add(Enrollment(student_id=s.id, batch_id=b.id))
                    print(f" - Enrolled {s.first_name} in {b.name}")
        
        await db.commit()
        print("Data assignments fixed!")

if __name__ == "__main__":
    asyncio.run(fix_data())
