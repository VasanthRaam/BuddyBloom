import uuid
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Homework, HomeworkSubmission, User, Batch, Student, Enrollment
from app.schemas.homework import HomeworkCreate
from app.services.notification_service import NotificationService

class HomeworkService:
    @staticmethod
    async def create_homework(db: AsyncSession, teacher_id: uuid.UUID, hw_in: HomeworkCreate):
        db_hw = Homework(
            id=uuid.uuid4(),
            teacher_id=teacher_id,
            batch_id=hw_in.batch_id,
            title=hw_in.title,
            description=hw_in.description,
            due_date=hw_in.due_date
        )
        db.add(db_hw)
        await db.flush()

        # Notify students
        await NotificationService.notify_students_for_homework(
            db, hw_in.batch_id, hw_in.title, hw_in.description, db_hw.id
        )

        await db.commit()
        return await HomeworkService.get_homework(db, db_hw.id)

    @staticmethod
    async def get_homework(db: AsyncSession, homework_id: uuid.UUID):
        query = select(Homework).where(Homework.id == homework_id)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_batch_homeworks(db: AsyncSession, batch_id: uuid.UUID):
        query = select(Homework).where(Homework.batch_id == batch_id).order_by(Homework.created_at.desc())
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_user_homeworks(db: AsyncSession, user_id: uuid.UUID, role: str):
        if role == "teacher":
            query = select(Homework).where(Homework.teacher_id == user_id)
        elif role == "student":
            # Get batches the student is enrolled in
            enroll_query = select(Enrollment.batch_id).join(Student).where(Student.user_id == user_id)
            enroll_res = await db.execute(enroll_query)
            batch_ids = enroll_res.scalars().all()
            
            if not batch_ids:
                return []
                
            query = select(Homework).where(Homework.batch_id.in_(batch_ids))
        else:
            query = select(Homework) # Admin see all
            
        result = await db.execute(query.order_by(Homework.created_at.desc()))
        homeworks = result.scalars().all()
        
        # Attach completion status for students
        if role == "student":
            for hw in homeworks:
                sub_query = select(HomeworkSubmission).where(
                    HomeworkSubmission.homework_id == hw.id,
                    HomeworkSubmission.student_id == user_id
                )
                sub_res = await db.execute(sub_query)
                submission = sub_res.scalars().first()
                # Dynamically set a temporary attribute for the schema to pick up
                hw.is_completed = submission.is_completed if submission else False
        
        return homeworks

    @staticmethod
    async def toggle_homework_complete(db: AsyncSession, homework_id: uuid.UUID, student_id: uuid.UUID):
        # Check if submission exists
        query = select(HomeworkSubmission).where(
            HomeworkSubmission.homework_id == homework_id,
            HomeworkSubmission.student_id == student_id
        )
        result = await db.execute(query)
        submission = result.scalars().first()

        if submission:
            submission.is_completed = not submission.is_completed
        else:
            submission = HomeworkSubmission(
                id=uuid.uuid4(),
                homework_id=homework_id,
                student_id=student_id,
                is_completed=True
            )
            db.add(submission)
        
        await db.commit()
        return submission.is_completed
