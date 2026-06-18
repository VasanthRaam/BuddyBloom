import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

engine = create_async_engine(DATABASE_URL, echo=True)

async def run_migration():
    async with engine.begin() as conn:
        print("Creating mobile_login_otps table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mobile_login_otps (
                id UUID PRIMARY KEY,
                phone VARCHAR NOT NULL,
                otp VARCHAR(6) NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                is_used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """))
        print("Table created successfully!")

if __name__ == "__main__":
    asyncio.run(run_migration())
