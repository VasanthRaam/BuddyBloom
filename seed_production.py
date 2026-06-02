import asyncio
from app.db.database import engine
from app.db.models import Base, User, UserRole
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
import uuid

async def seed():
    print("Checking production database...")
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as session:
        # Check if admin exists
        res = await session.execute(select(User).where(User.email == "admin@buddybloom.com"))
        admin = res.scalars().first()
        
        if not admin:
            print("Creating Admin user...")
            new_admin = User(
                id=uuid.uuid4(),
                email="admin@buddybloom.com",
                full_name="BuddyBloom Admin",
                role=UserRole.admin,
                is_approved=True
            )
            session.add(new_admin)
            await session.commit()
            print("Admin created successfully.")
        else:
            print("Admin already exists.")

if __name__ == "__main__":
    asyncio.run(seed())
