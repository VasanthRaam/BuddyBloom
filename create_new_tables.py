import asyncio
from app.db.database import engine
from app.db.models import Base

async def create_tables():
    async with engine.begin() as conn:
        # This will create any missing tables (like user_push_tokens)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables updated successfully.")

if __name__ == "__main__":
    asyncio.run(create_tables())
