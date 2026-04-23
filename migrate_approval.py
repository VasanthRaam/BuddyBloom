"""
Migration: Add is_approved to users, create pending_registrations table.
Run once: venv\Scripts\python migrate_approval.py
"""
import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

MIGRATION_SQL = """
-- Add is_approved column to users if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='users' AND column_name='is_approved'
    ) THEN
        ALTER TABLE users ADD COLUMN is_approved BOOLEAN NOT NULL DEFAULT false;
    END IF;
END
$$;

-- Mark all existing users as approved so current accounts keep working
UPDATE users SET is_approved = true WHERE is_approved = false;

-- Create pending_registrations table
CREATE TABLE IF NOT EXISTS pending_registrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR NOT NULL,
    email VARCHAR NOT NULL UNIQUE,
    phone VARCHAR,
    hashed_temp_password VARCHAR NOT NULL,
    role user_role NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'pending',
    rejection_reason VARCHAR,
    created_at TIMESTAMPTZ DEFAULT now()
);
"""

async def run():
    async with AsyncSessionLocal() as db:
        # Step 1: Add is_approved column if missing
        await db.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='users' AND column_name='is_approved'
                ) THEN
                    ALTER TABLE users ADD COLUMN is_approved BOOLEAN NOT NULL DEFAULT false;
                END IF;
            END
            $$;
        """))
        await db.commit()

        # Step 2: Mark all existing users as approved
        await db.execute(text("UPDATE users SET is_approved = true WHERE is_approved = false;"))
        await db.commit()

        # Step 3: Create pending_registrations table
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS pending_registrations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                full_name VARCHAR NOT NULL,
                email VARCHAR NOT NULL UNIQUE,
                phone VARCHAR,
                hashed_temp_password VARCHAR NOT NULL,
                role user_role NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                rejection_reason VARCHAR,
                created_at TIMESTAMPTZ DEFAULT now()
            );
        """))
        await db.commit()

        print("Migration complete.")
        print("  - Added is_approved to users (all existing users marked approved).")
        print("  - Created pending_registrations table.")


if __name__ == "__main__":
    asyncio.run(run())
