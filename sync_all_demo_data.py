import asyncio
import sys
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import Student, Enrollment, Batch, User, UserRole, Quiz

async def sync_data():
    if sys.stdout.encoding != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
    async with AsyncSessionLocal() as db:
        # 1. Get Teacher and Admin
        teacher = (await db.execute(select(User).where(User.email == 'nithya@gmail.com'))).scalars().first()
        admin = (await db.execute(select(User).where(User.email == 'revathi@gmail.com'))).scalars().first()
        student_user = (await db.execute(select(User).where(User.email == 'vasanthraam1@gmail.com'))).scalars().first()
        
        # 2. Get Student Profile
        student_profile = (await db.execute(select(Student))).scalars().first()
        
        if student_profile and student_user:
            student_profile.user_id = student_user.id
            print(f"Linked student {student_profile.first_name} to user {student_user.email}")

        # 3. Get all batches and assign them to the teacher
        batches = (await db.execute(select(Batch))).scalars().all()
        for b in batches:
            if teacher:
                b.teacher_id = teacher.id
                print(f"Assigned batch {b.name} to teacher {teacher.email}")
            
            # Enroll the student in this batch
            if student_profile:
                # Check if already enrolled
                e_res = await db.execute(select(Enrollment).where(Enrollment.student_id == student_profile.id, Enrollment.batch_id == b.id))
                if not e_res.scalars().first():
                    db.add(Enrollment(student_id=student_profile.id, batch_id=b.id))
                    print(f"Enrolled {student_profile.first_name} in {b.name}")

        # 4. Ensure Quizzes are visible
        # If any quiz has no creator, assign it to the admin
        quizzes = (await db.execute(select(Quiz))).scalars().all()
        for q in quizzes:
            if q.created_by is None and admin:
                q.created_by = admin.id
                print(f"Assigned quiz {q.title} to admin {admin.email}")

        await db.commit()
        print("\n✅ All data synced for demo!")

if __name__ == "__main__":
    asyncio.run(sync_data())
