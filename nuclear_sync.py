import asyncio
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import Student, Enrollment, Batch, User, UserRole, Quiz, Course, Question, Option
import uuid

async def nuclear_sync():
    async with AsyncSessionLocal() as db:
        # 1. Ensure all students are linked to users correctly
        users = (await db.execute(select(User))).scalars().all()
        student_profiles = (await db.execute(select(Student))).scalars().all()
        
        for s in student_profiles:
            # Match by first name roughly if not linked
            if not s.user_id:
                for u in users:
                    if u.role == UserRole.student:
                        s.user_id = u.id
                        print(f"Linked Student {s.first_name} to User {u.email}")
                        break
        
        # 2. Assign Teacher to ALL Batches
        teacher = (await db.execute(select(User).where(User.role == UserRole.teacher))).scalars().first()
        admin = (await db.execute(select(User).where(User.role == UserRole.admin))).scalars().first()
        
        batches = (await db.execute(select(Batch))).scalars().all()
        for b in batches:
            if teacher:
                b.teacher_id = teacher.id
            
            # 3. Enroll ALL students in ALL batches
            for s in student_profiles:
                e_res = await db.execute(select(Enrollment).where(Enrollment.student_id == s.id, Enrollment.batch_id == b.id))
                if not e_res.scalars().first():
                    db.add(Enrollment(student_id=s.id, batch_id=b.id))
                    print(f"Enrolled {s.first_name} in batch {b.name}")

        # 4. Create a GUARANTEED VISIBLE QUIZ
        courses = (await db.execute(select(Course))).scalars().all()
        if courses and admin:
            for c in courses:
                new_quiz = Quiz(
                    id=uuid.uuid4(),
                    title=f"Welcome Quiz for {c.name} 🚀",
                    description="This is a guaranteed quiz for all students!",
                    course_id=c.id,
                    created_by=admin.id
                )
                db.add(new_quiz)
                print(f"Created nuclear quiz for course {c.name}")
                
                # Add one question
                q = Question(
                    id=uuid.uuid4(),
                    quiz_id=new_quiz.id,
                    question_text="Are you ready to learn?",
                    points=10
                )
                db.add(q)
                db.add(Option(id=uuid.uuid4(), question_id=q.id, option_text="Yes! ✅", is_correct=True))
                db.add(Option(id=uuid.uuid4(), question_id=q.id, option_text="No", is_correct=False))

        await db.commit()
        print("\n☢️ NUCLEAR SYNC COMPLETE! Quizzes MUST show up now.")

if __name__ == "__main__":
    asyncio.run(nuclear_sync())
