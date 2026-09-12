import asyncio
import sys
from app.db.database import AsyncSessionLocal
from app.db.models import User, UserPushToken
from sqlalchemy.future import select
from app.services.notification_service import NotificationService
from app.core.firebase import init_firebase_admin

async def trigger_test_push(target_email: str = None):
    # Ensure Firebase Admin SDK is initialized
    init_firebase_admin()

    async with AsyncSessionLocal() as db:
        query = select(User)
        if target_email:
            query = query.where(User.email == target_email)
            
        result = await db.execute(query)
        users = result.scalars().all()
        
        if not users:
            print(f"[-] No user found matching: {target_email}")
            return

        for user in users:
            token_res = await db.execute(select(UserPushToken).where(UserPushToken.user_id == user.id))
            tokens = token_res.scalars().all()
            if tokens:
                print(f"[PUSH-TEST] Triggering manual push notification to {user.full_name} ({user.email}) across {len(tokens)} token(s)...")
                await NotificationService.send_push_notification(
                    db=db,
                    user_id=user.id,
                    title="Real-Time Test Push Alert",
                    message="Hello! This is a manual real-time push notification test to your APK.",
                    data={"type": "manual_test", "timestamp": str(asyncio.get_event_loop().time())}
                )
                print(f"[PUSH-TEST] Push notification sent to {user.full_name}!")


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(trigger_test_push(email))
