import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

async def check_constraints():
    async with AsyncSessionLocal() as db:
        query = text("""
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE n.nspname = 'public' AND conrelid = 'users'::regclass;
        """)
        res = await db.execute(query)
        for row in res:
            print(f"Constraint: {row[0]} -> {row[1]}")

if __name__ == "__main__":
    asyncio.run(check_constraints())
