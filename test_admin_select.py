import asyncio
from app.db.database import AsyncSessionLocal
from app.db.models import User, UserRole, UserPushToken
from sqlalchemy.future import select

async def run_test():
    async with AsyncSessionLocal() as session:
        print("[i] Fetching admins query...")
        query = select(User).where(User.role == UserRole.admin)
        res = await session.execute(query)
        admins = res.scalars().all()
        print(f"[+] Found {len(admins)} admin(s)")
        for a in admins:
            print(f"  Admin: {a.email} (ID: {a.id}) | Role: {a.role}")
            
            # Find their push tokens
            t_res = await session.execute(
                select(UserPushToken).where(UserPushToken.user_id == a.id)
            )
            tokens = t_res.scalars().all()
            print(f"  Push Tokens: {len(tokens)}")
            for t in tokens:
                print(f"    Token: {t.push_token[:40]}... | Device: {t.device_type}")
                
if __name__ == "__main__":
    asyncio.run(run_test())
