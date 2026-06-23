import asyncio
from app.db.database import engine
from sqlalchemy import text

async def migrate():
    print("Migrating database tables for manual fee indicators...")
    async with engine.begin() as conn:
        try:
            # 1. Add is_manual to fee_payments
            await conn.execute(text("ALTER TABLE fee_payments ADD COLUMN IF NOT EXISTS is_manual BOOLEAN DEFAULT FALSE"))
            # 2. Add student_id to incomes
            await conn.execute(text("ALTER TABLE incomes ADD COLUMN IF NOT EXISTS student_id UUID REFERENCES users(id) ON DELETE SET NULL"))
            print("Migration successful.")
        except Exception as e:
            print(f"Migration error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
