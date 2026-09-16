import asyncio
from sqlalchemy import text
from app.db.database import engine

async def fix_schema():
    async with engine.begin() as conn:
        print("Making student_id nullable...")
        try:
            await conn.execute(text('ALTER TABLE pending_enrollments ALTER COLUMN student_id DROP NOT NULL;'))
        except Exception as e:
            print("Error altering student_id (maybe already nullable?):", e)
            
        print("Adding teacher_id to pending_enrollments...")
        try:
            await conn.execute(text('ALTER TABLE pending_enrollments ADD COLUMN IF NOT EXISTS teacher_id UUID REFERENCES users(id) ON DELETE CASCADE;'))
        except Exception as e:
            print("Error adding teacher_id (maybe already added?):", e)

    print("Schema updated successfully!")

if __name__ == '__main__':
    asyncio.run(fix_schema())
