import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from app.db.models import Student, Enrollment, Batch, Notification, UserPushToken

class NotificationService:
    @staticmethod
    async def send_push_notification(db: AsyncSession, user_id: UUID, title: str, message: str, data: dict = None):
        """
        Send a real-time push notification via Expo Push API & FCM to all devices registered for this user.
        """
        query = select(UserPushToken.push_token).where(UserPushToken.user_id == user_id)
        result = await db.execute(query)
        tokens = result.scalars().all()
        
        if not tokens:
            print(f"[PUSH] No registered push tokens found for user_id={user_id}")
            return
            
        print(f"[PUSH] Sending real-time push to user {user_id} across {len(tokens)} device token(s): '{title}'")
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
            
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=messages)
                print(f"[PUSH-RESPONSE] Status {response.status_code}: {response.text}")
            except Exception as e:
                print(f"[PUSH-ERROR] Failed to send push notification to user {user_id}: {e}")

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
    @staticmethod
    async def notify_admins_new_registration(db: AsyncSession, new_user_name: str, new_user_role: str):
        """
        Notify all administrators when a new user registers.
        """
        from app.db.models import User, UserRole
        
        # Find all admins
        query = select(User.id).where(User.role == UserRole.admin)
        result = await db.execute(query)
        admin_ids = result.scalars().all()
        
        title = "New Registration! 🔔"
        message = f"{new_user_name} has registered as a {new_user_role} and is awaiting your approval."
        
        for aid in admin_ids:
            # 1. Save In-App Notification
            db_notification = Notification(
                user_id=aid,
                title=title,
                message=message,
                link_to="PendingApprovals"
            )
            db.add(db_notification)
            
            # 2. Trigger Real-Time Push Notification
            await NotificationService.send_push_notification(
                db, 
                aid, 
                title, 
                message, 
                {"type": "registration_request", "action": "approval"}
            )
        
        await db.commit()
        return len(admin_ids)

    @staticmethod
    async def notify_all_students_for_holiday(db: AsyncSession, holiday_date, description: str = ""):
        """
        Notify all students about a new academy holiday.
        """
        from app.db.models import User, UserRole
        
        # Find all student users
        query = select(User.id).where(User.role == UserRole.student)
        result = await db.execute(query)
        student_ids = result.scalars().all()
        
        title = "Academy Holiday! 🏖️"
        message = f"Academy has declared a holiday on {holiday_date.strftime('%Y-%m-%d')}."
        if description:
            message += f" ({description})"
            
        for sid in student_ids:
            # 1. Save In-App Notification
            db_notification = Notification(
                user_id=sid,
                title=title,
                message=message,
                link_to="Attendance"
            )
            db.add(db_notification)
            
            # 2. Trigger Real-Time Push Notification
            await NotificationService.send_push_notification(
                db, 
                sid, 
                title, 
                message, 
                {"type": "holiday", "date": str(holiday_date)}
            )
            
        await db.commit()
        return len(student_ids)
