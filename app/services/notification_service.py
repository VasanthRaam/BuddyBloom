import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from app.db.models import Student, Enrollment, Batch, Notification, UserPushToken

class NotificationService:
    @staticmethod
    async def send_push_notification(db: AsyncSession, user_id: UUID, title: str, message: str, data: dict = None):
        """
        Send a real-time push notification via Expo Push API to all devices registered for this user.
        """
        query = select(UserPushToken.push_token).where(UserPushToken.user_id == user_id)
        result = await db.execute(query)
        tokens = result.scalars().all()
        
        if not tokens:
            return
            
        url = "https://exp.host/--/api/v2/push/send"
        messages = []
        for token in tokens:
            msg = {
                "to": token,
                "title": title,
                "body": message,
                "sound": "default",
                "priority": "high",
                "channelId": "default"
            }
            if data:
                msg["data"] = data
            messages.append(msg)
            
        async with httpx.AsyncClient() as client:
            try:
                # Expo allows sending up to 100 messages in a single request
                response = await client.post(url, json=messages)
                if response.status_code != 200:
                    print(f"⚠️ [PUSH] Expo API returned error: {response.text}")
                else:
                    print(f"🚀 [PUSH] Notification sent to user {user_id} ({len(tokens)} devices)")
            except Exception as e:
                print(f"❌ [PUSH] Failed to send notification to user {user_id}: {e}")

    @staticmethod
    async def notify_students_for_new_quiz(db: AsyncSession, course_id: UUID, quiz_id: UUID, quiz_title: str):
        """
        Identify students enrolled in batches for this course and send a notification.
        """
        query = select(Student).distinct().join(Enrollment).join(Batch).where(Batch.course_id == course_id)
        result = await db.execute(query)
        students = result.scalars().all()
        
        title = "New Quiz Available! 📝"
        message = f"A new quiz '{quiz_title}' has been posted. Good luck!"
        
        for s in students:
            # 1. Save In-App Notification
            db_notification = Notification(
                user_id=s.user_id,
                title=title,
                message=message,
                link_to=f"Quiz:{quiz_id}"
            )
            db.add(db_notification)
            
            # 2. Trigger Real-Time Push Notification
            await NotificationService.send_push_notification(
                db, 
                s.user_id, 
                title, 
                message, 
                {"type": "quiz", "id": str(quiz_id)}
            )
        
        await db.commit()
        return len(students)

    @staticmethod
    async def notify_students_for_homework(db: AsyncSession, batch_id: UUID, homework_id: UUID, title: str, description: str = "", student_id: UUID = None):
        """
        Notify students about new homework. If student_id is provided, only notify that student.
        """
        if student_id:
            user_ids = [student_id]
        else:
            query = select(Student.user_id).join(Enrollment).where(Enrollment.batch_id == batch_id)
            result = await db.execute(query)
            user_ids = result.scalars().all()
        
        desc_snippet = f": {description[:50]}..." if description else ""
        notif_title = "New Homework Assigned! 📚"
        notif_message = f"New assignment: '{title}'{desc_snippet}. Check your dashboard for details."
        
        for uid in user_ids:
            # 1. Save In-App Notification
            db_notification = Notification(
                user_id=uid,
                title=notif_title,
                message=notif_message,
                link_to=f"Homework:{homework_id}"
            )
            db.add(db_notification)
            
            # 2. Trigger Real-Time Push Notification
            await NotificationService.send_push_notification(
                db, 
                uid, 
                notif_title, 
                notif_message, 
                {"type": "homework", "id": str(homework_id)}
            )
        
        await db.commit()
        return len(user_ids)

