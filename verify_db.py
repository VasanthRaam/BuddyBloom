import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

async def check():
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text('SELECT * FROM homework LIMIT 0'))
            print("SUCCESS: Homework table exists and is accessible.")
            
            # Check columns
            res = await db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'homework'"))
            cols = [r[0] for r in res]
            print(f"Columns: {cols}")
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check())
