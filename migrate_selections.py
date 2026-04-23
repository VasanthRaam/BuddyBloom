import asyncio
from app.db.database import engine
from sqlalchemy import text

async def migrate():
    print("Migrating pending_registrations table...")
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS selected_course_ids UUID[]"))
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS selected_batch_ids UUID[]"))
            print("Migration successful.")
        except Exception as e:
            print(f"Migration error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
