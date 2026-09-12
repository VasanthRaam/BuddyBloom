import asyncio
from app.db.database import AsyncSessionLocal
from app.db.models import UserPushToken, User
from sqlalchemy.future import select

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(User.email, User.full_name, User.role, UserPushToken.device_type, UserPushToken.push_token)
            .join(UserPushToken, User.id == UserPushToken.user_id)
        )
        rows = res.all()
        print(f"Total registered push tokens in DB: {len(rows)}")
        for email, name, role, dtype, token in rows:
            print(f"- User: {name} ({email}, {role}) | Device: {dtype} | Token: {token[:30]}...")

if __name__ == "__main__":
    asyncio.run(check())
