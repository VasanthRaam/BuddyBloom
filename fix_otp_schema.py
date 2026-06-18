import asyncio
from app.db.database import engine, Base
from app.db.models import PasswordResetOTP

async def create_table():
    async with engine.begin() as conn:
        print("Creating PasswordResetOTP table...")
        await conn.run_sync(PasswordResetOTP.__table__.create, checkfirst=True)
        print("Done!")

if __name__ == "__main__":
    asyncio.run(create_table())
