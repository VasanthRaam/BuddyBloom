import asyncio
from app.db.database import engine, Base
from app.db.models import Income

async def create_income_table():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Income table created (or verified).")

if __name__ == "__main__":
    asyncio.run(create_income_table())
