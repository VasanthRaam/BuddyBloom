from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from app.db.models import Student, Enrollment, Batch, Notification

class NotificationService:
    @staticmethod
    async def notify_students_for_new_quiz(db: AsyncSession, course_id: UUID, quiz_id: UUID, quiz_title: str):
        """
        Identify students enrolled in batches for this course and send a notification.
        """
        # Find all students enrolled in any batch of this course
        query = select(Student).distinct().join(Enrollment).join(Batch).where(Batch.course_id == course_id)
        result = await db.execute(query)
        students = result.scalars().all()
        
        print(f"\n🔔 [NOTIFICATION] Sending alerts to {len(students)} students for new quiz: '{quiz_title}'")
        
        for s in students:
            # Save In-App Notification
            db_notification = Notification(
                user_id=s.user_id,
                title="New Quiz Available! 📝",
                message=f"A new quiz '{quiz_title}' has been posted. Good luck!",
                link_to=f"Quiz:{quiz_id}"
            )
            db.add(db_notification)
            print(f"   -> Saved In-App Notification for {s.first_name} {s.last_name}")
        
        await db.commit()
        return len(students)

    @staticmethod
    async def notify_students_for_homework(db: AsyncSession, batch_id: UUID, homework_id: UUID, title: str, description: str = "", student_id: UUID = None):
        """
        Notify students about new homework. If student_id is provided, only notify that student.
        """
        if student_id:
            # We already have the user_id (student_id in homework table refers to users.id)
            user_ids = [student_id]
        else:
            # Notify everyone in the batch
            query = select(Student.user_id).join(Enrollment).where(Enrollment.batch_id == batch_id)
            result = await db.execute(query)
            user_ids = result.scalars().all()
        
        desc_snippet = f": {description[:50]}..." if description else ""
        
        for uid in user_ids:
            db_notification = Notification(
                user_id=uid,
                title="New Homework Assigned! 📚",
                message=f"New assignment: '{title}'{desc_snippet}. Check your dashboard for details.",
                link_to=f"Homework:{homework_id}"
            )
            db.add(db_notification)
        
        await db.commit()
        return len(user_ids)

