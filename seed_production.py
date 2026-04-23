import asyncio
import uuid
from sqlalchemy.future import select
from sqlalchemy import text
from app.db.database import AsyncSessionLocal
from app.db.models import User, UserRole, Student, Batch, Course, Enrollment

async def seed_data():
    async with AsyncSessionLocal() as db:
        print("Cleaning up old data...")
        # Drop the Supabase auth dependency for local seeding
        try:
            await db.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_id_fkey;"))
            await db.commit()
        except Exception as e:
            print(f"Note: Could not drop constraint (might not exist): {e}")

        # Use CASCADE to ensure all dependent rows are deleted
        await db.execute(text("TRUNCATE TABLE enrollments, attendance, homework_submissions, homework, notifications, students, batches, courses, users CASCADE;"))
        await db.commit()

        print("Creating Course...")
        course = Course(id=uuid.uuid4(), name="BuddyBloom Excellence Program", description="Main Academy Course")
        db.add(course)
        await db.commit()
        await db.refresh(course)

        print("Creating Admin...")
        admin = User(
            id=uuid.uuid4(),
            role=UserRole.admin,
            full_name="Academy Administrator",
            email="admin@buddybloom.com",
            phone="1234567890"
        )
        db.add(admin)
        await db.commit()

        print("Creating Teachers...")
        teachers = []
        for i in range(1, 3):
            teacher = User(
                id=uuid.uuid4(),
                role=UserRole.teacher,
                full_name=f"Teacher {i}",
                email=f"teacher{i}@buddybloom.com",
                phone=f"987654321{i}"
            )
            db.add(teacher)
            teachers.append(teacher)
        await db.commit()

        print("Creating Batches...")
        batches = []
        for i, teacher in enumerate(teachers):
            for j in range(1, 3):
                batch = Batch(
                    id=uuid.uuid4(),
                    course_id=course.id,
                    teacher_id=teacher.id,
                    name=f"Batch {i+1}-{chr(64+j)}"
                )
                db.add(batch)
                batches.append(batch)
        await db.commit()

        print("Creating Students and Parents...")
        student_count = 1
        for batch in batches:
            for k in range(1, 4):
                # Parent
                parent = User(
                    id=uuid.uuid4(),
                    role=UserRole.parent,
                    full_name=f"Parent {student_count}",
                    email=f"parent{student_count}@example.com"
                )
                db.add(parent)
                await db.flush()

                # Student User
                student_user = User(
                    id=uuid.uuid4(),
                    role=UserRole.student,
                    full_name=f"Student {student_count}",
                    email=f"student{student_count}@example.com"
                )
                db.add(student_user)
                await db.flush()

                # Student Profile
                student_profile = Student(
                    id=uuid.uuid4(),
                    user_id=student_user.id,
                    parent_id=parent.id,
                    first_name="Student",
                    last_name=str(student_count)
                )
                db.add(student_profile)
                await db.flush()

                # Enrollment
                enroll = Enrollment(
                    id=uuid.uuid4(),
                    student_id=student_profile.id,
                    batch_id=batch.id
                )
                db.add(enroll)
                student_count += 1
            await db.commit()

        print(f"Success! Created 1 admin, 2 teachers, 4 batches, and 12 student-parent pairs.")
        print("\nNOTE: These IDs are random. If you are using Supabase Auth, you will need to map these 'sub' IDs to your actual auth users.")

if __name__ == "__main__":
    asyncio.run(seed_data())
