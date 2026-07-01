import asyncio
from app.db.database import AsyncSessionLocal
from app.db.models import User, UserPushToken
from sqlalchemy.future import select
from app.services.notification_service import NotificationService

async def send_emergency_test(email):
    async with AsyncSessionLocal() as db:
        # Find user
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if not user:
            print(f"[-] User with email {email} not found.")
            return

        print(f"[i] Found user {user.full_name}. Checking for push tokens...")
        
        # Find tokens
        result = await db.execute(select(UserPushToken).where(UserPushToken.user_id == user.id))
        tokens = result.scalars().all()
        
        if not tokens:
            print(f"[-] No push tokens found for {email}. Did you log in on the phone at least once?")
            return

        print(f"[i] Sending test notification to {len(tokens)} device(s)...")
        
        title = "BuddyBloom Test"
        message = f"Your login is {email}. This notification reached you successfully!"
        
        await NotificationService.send_push_notification(
            db, 
            user.id, 
            title, 
            message, 
            {"type": "test"}
        )
        print("[+] Done! Check your phone now.")

if __name__ == "__main__":
    import sys
    email = sys.argv[1] if len(sys.argv) > 1 else "vasanth@example.com"
    asyncio.run(send_emergency_test(email))
