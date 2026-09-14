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
        
        expo_tokens = [t for t in tokens if t.startswith("ExponentPushToken[") or t.startswith("ExpoPushToken[")]
        fcm_tokens = [t for t in tokens if t not in expo_tokens and not t.startswith("flutter_device_")]

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Send to Expo tokens
            if expo_tokens:
                expo_url = "https://exp.host/--/api/v2/push/send"
                expo_messages = [
                    {
                        "to": t,
                        "title": title,
                        "body": message,
                        "sound": "default",
                        "priority": "high",
                        "data": data or {}
                    }
                    for t in expo_tokens
                ]
                try:
                    res = await client.post(expo_url, json=expo_messages)
                    print(f"[PUSH-EXPO] Status {res.status_code}: {res.text}")
                except Exception as e:
                    print(f"[PUSH-EXPO-ERROR] {e}")

            # 2. Send to FCM tokens
            if fcm_tokens:
                try:
                    import firebase_admin
                    from firebase_admin import messaging
                    from app.core.firebase import init_firebase_admin

                    if not firebase_admin._apps:
                        init_firebase_admin()

                    if not firebase_admin._apps:
                        print("[PUSH-FCM-ERROR] Firebase Admin SDK is not initialized!")
                    else:

                        for fcm_t in fcm_tokens:
                            try:
                                # Convert all values in data dict to strings for FCM
                                stringified_data = {str(k): str(v) for k, v in (data or {}).items()}
                                msg = messaging.Message(
                                    notification=messaging.Notification(
                                        title=title,
                                        body=message,
                                    ),
                                    data=stringified_data,
                                    token=fcm_t,
                                    android=messaging.AndroidConfig(
                                        priority='high',
                                        notification=messaging.AndroidNotification(
                                            sound='default',
                                            default_sound=True,
                                        )
                                    ),
                                    apns=messaging.APNSConfig(
                                        payload=messaging.APNSPayload(
                                            aps=messaging.Aps(sound='default')
                                        )
                                    )
                                )
                                response = messaging.send(msg)
                                print(f"[PUSH-FCM] Successfully sent message: {response}")
                            except Exception as token_err:
                                print(f"[PUSH-FCM-ERROR] Error sending to token {fcm_t}: {token_err}")
                                if "NotRegistered" in str(token_err) or "Unregistered" in str(token_err):
                                    try:
                                        from sqlalchemy import delete
                                        await db.execute(delete(UserPushToken).where(UserPushToken.push_token == fcm_t))
                                        await db.commit()
                                        print(f"[PUSH-CLEANUP] Removed stale token from DB: {fcm_t[:30]}...")
                                    except Exception as clean_err:
                                        print(f"[PUSH-CLEANUP-ERROR] Failed to remove stale token: {clean_err}")
                except Exception as e:
                    print(f"[PUSH-FCM-ERROR] Global FCM error: {e}")


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

    @staticmethod
    async def notify_quiz_result(
        db: AsyncSession,
        user_id: UUID,
        quiz_title: str,
        total_score: int,
        max_score: int,
        xp_earned: int = 0,
    ):
        """
        Notify the student after their quiz is evaluated:
        tells them their score and XP earned.
        """
        pct = int((total_score / max_score * 100)) if max_score > 0 else 0
        xp_str = f" (+{xp_earned} XP)" if xp_earned > 0 else ""
        title = "Quiz Completed! 🎯"
        message = f"You scored {total_score}/{max_score} ({pct}%){xp_str} on '{quiz_title}'."

        db_notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            link_to="QuizResults"
        )
        db.add(db_notification)
        await db.commit()

        await NotificationService.send_push_notification(
            db,
            user_id,
            title,
            message,
            {"type": "quiz_result", "score": str(total_score), "max_score": str(max_score), "xp_earned": str(xp_earned)},
        )

    @staticmethod
    async def notify_fee_paid(
        db: AsyncSession,
        student_name: str,
        amount: float,
        course_name: str = "",
    ):
        """
        Notify all admins when a student's fee payment is confirmed.
        """
        from app.db.models import User, UserRole
        query = select(User.id).where(User.role == UserRole.admin)
        result = await db.execute(query)
        admin_ids = result.scalars().all()

        title = "Fee Payment Received 💳"
        course_str = f" for {course_name}" if course_name else ""
        message = f"{student_name} paid ₹{amount:,.0f}{course_str}."

        for aid in admin_ids:
            db_notification = Notification(
                user_id=aid,
                title=title,
                message=message,
                link_to="Revenue"
            )
            db.add(db_notification)

        await db.commit()

        for aid in admin_ids:
            await NotificationService.send_push_notification(
                db,
                aid,
                title,
                message,
                {"type": "fee_payment", "screen": "Revenue"},
            )

    @staticmethod
    async def notify_student_fee_due(
        db: AsyncSession,
        user_id: UUID,
        amount: float,
        due_date: str,
        course_name: str = "",
    ):
        """
        Notify student/parent that a fee payment is due.
        """
        title = "Fee Due Reminder 🔔"
        course_str = f" for {course_name}" if course_name else ""
        message = f"Your fee of ₹{amount:,.0f}{course_str} is due on {due_date}. Please pay on time."

        db_notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            link_to="Fees"
        )
        db.add(db_notification)
        await db.commit()

        await NotificationService.send_push_notification(
            db,
            user_id,
            title,
            message,
            {"type": "fee_due", "screen": "Fees"},
        )

