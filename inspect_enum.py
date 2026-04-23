import asyncio
import os
import sys

# Add the current directory to sys.path to find 'app'
sys.path.append(os.getcwd())

from sqlalchemy import text
from app.db.database import engine

async def inspect_enum():
    async with engine.connect() as conn:
        try:
            # Query to get values of the 'user_role' enum
            result = await conn.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
                WHERE pg_type.typname = 'user_role'
                ORDER BY enumsortorder;
            """))
            labels = [row[0] for row in result]
            print(f"Enum 'user_role' labels in DB: {labels}")
        except Exception as e:
            print(f"Failed to inspect enum: {e}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(inspect_enum())
