import asyncio
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select
from app.db.database import SessionLocal
from app.db.models import User, Student, FeePayment, Homework, Batch, QuizAttempt

async def seed_dashboard_data():
    async with SessionLocal() as db:
        # Get Admin and a Teacher
        admin_res = await db.execute(select(User).where(User.role == "admin"))
        admin = admin_res.scalars().first()
        
        teacher_res = await db.execute(select(User).where(User.role == "teacher"))
        teacher = teacher_res.scalars().first()
        
        if not admin or not teacher:
            print("Admin or Teacher not found. Run sync_all_demo_data.py first.")
            return

        # Seed Fee Payments (Revenue)
        students_res = await db.execute(select(User).where(User.role == "student"))
        students = students_res.scalars().all()
        
        for i, student in enumerate(students):
            # Pending fees
            db.add(FeePayment(
                id=uuid.uuid4(),
                user_id=student.id,
                amount=500.0,
                status="pending" if i % 3 == 0 else "paid",
                due_date=datetime.utcnow() + timedelta(days=10),
                paid_at=datetime.utcnow() if i % 3 != 0 else None
            ))
            
        # Seed Homework
        batch_res = await db.execute(select(Batch))
        batches = batch_res.scalars().all()
        if batches:
            db.add(Homework(
                id=uuid.uuid4(),
                teacher_id=teacher.id,
                batch_id=batches[0].id,
                title="Mathematics Worksheet #1",
                description="Complete all equations on page 42.",
                due_date=datetime.utcnow() + timedelta(days=2)
            ))
            
        await db.commit()
        print("Dashboard mock data seeded! 🚀")

if __name__ == "__main__":
    asyncio.run(seed_dashboard_data())
