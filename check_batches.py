import asyncio
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import Batch

async def get_batches():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Batch))
        batches = res.scalars().all()
        print('Batch count:', len(batches))
        for b in batches:
            print(f"Batch: {b.name}")

if __name__ == "__main__":
    asyncio.run(get_batches())
