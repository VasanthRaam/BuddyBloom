import asyncio
import os
import sys

# Add the current directory to sys.path to find 'app'
sys.path.append(os.getcwd())

from app.db.database import engine, Base
from app.db.models import User, Student # Import models to register them with Base

async def create_tables():
    print("Creating tables...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Tables created successfully!")
    except Exception as e:
        print(f"Failed to create tables: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_tables())
