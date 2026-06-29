import asyncio
from app.db.database import engine
from app.db.models import Base, User, UserRole
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import uuid

async def wipe_and_seed():
    print("Connecting to database...")
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    table_names = list(Base.metadata.tables.keys())
    print(f"Tables to wipe: {', '.join(table_names)}")
    
    async with engine.begin() as conn:
        print("Truncating all tables with CASCADE...")
        truncate_query = f"TRUNCATE TABLE {', '.join(table_names)} CASCADE;"
        await conn.execute(text(truncate_query))
        print("All tables truncated successfully.")
        
    async with async_session() as session:
        print("Creating Admin Google user...")
        # d012fbed-6ad2-406c-9457-190bb4104e96 corresponds to the Google Auth UUID for vasanthraam89@gmail.com
        admin_id = uuid.UUID("d012fbed-6ad2-406c-9457-190bb4104e96")
        new_admin = User(
            id=admin_id,
            email="vasanthraam89@gmail.com",
            full_name="Academy Administrator",
            role=UserRole.admin,
            is_approved=True
        )
        session.add(new_admin)
        await session.commit()
        print("Admin user successfully created in the database:")
        print(f"- Name: {new_admin.full_name}")
        print(f"- Email: {new_admin.email}")
        print(f"- Role: {new_admin.role}")
        print(f"- ID: {new_admin.id}")

if __name__ == "__main__":
    asyncio.run(wipe_and_seed())
