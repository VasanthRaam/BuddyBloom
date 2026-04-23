import asyncio
import os
import sys

# Add the current directory to sys.path to find 'app'
sys.path.append(os.getcwd())

from sqlalchemy import text
from app.db.database import engine

async def inspect_db():
    async with engine.connect() as conn:
        try:
            result = await conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public';
            """))
            print("\nTables in 'public' schema:")
            for row in result:
                print(f"Table: {row[0]}")
        except Exception as e:
            print(f"Failed to inspect: {e}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(inspect_db())
