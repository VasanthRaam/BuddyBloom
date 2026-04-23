import asyncio
from app.db.database import engine
from sqlalchemy import text

async def migrate():
    print("Migrating homework_submissions table...")
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE homework_submissions ADD COLUMN IF NOT EXISTS is_completed BOOLEAN DEFAULT FALSE"))
            print("Migration successful.")
        except Exception as e:
            print(f"Migration error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
