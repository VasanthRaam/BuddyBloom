import asyncio
import os
import sys

# Add the current directory to sys.path to find 'app'
sys.path.append(os.getcwd())

from sqlalchemy import text
from app.db.database import engine

async def inspect_quizzes():
    async with engine.connect() as conn:
        try:
            result = await conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'quizzes';
            """))
            print("\n--- Columns in 'quizzes' table ---")
            for row in result:
                print(f"Column: {row[0]}, Type: {row[1]}, Nullable: {row[2]}")
        except Exception as e:
            print(f"Failed: {e}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(inspect_quizzes())
