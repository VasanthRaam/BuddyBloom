from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api_v1.api import api_router

tags_metadata = [
    {
        "name": "users",
        "description": "Operations with users. The user ID matches the Supabase Auth UUID.",
    },
    {
        "name": "students",
        "description": "Manage student profiles and their relationships with parents.",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="BuddyBloom API - Academy Management Platform for Parents, Students, and Teachers.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
)

from app.core.middleware import SupabaseAuthMiddleware, NoCacheMiddleware, ResponseTimingMiddleware

# Add JWT Authentication and No-Cache Middleware
app.add_middleware(SupabaseAuthMiddleware)
app.add_middleware(NoCacheMiddleware)
app.add_middleware(ResponseTimingMiddleware)

# Set all CORS enabled origins
# Must be added LAST so it's the outermost middleware!
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://localhost:19006",
        "http://localhost:19000",
        "https://buddybloom.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup_event():
    try:
        from app.db.database import engine
        from sqlalchemy import text
        from app.db.models import Base
        async with engine.begin() as conn:
            # Create any missing tables (like user_push_tokens, expenses, etc.)
            await conn.run_sync(Base.metadata.create_all)
            # Ensure new columns exist on pending_registrations table
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS push_token VARCHAR;"))
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS selected_course_ids UUID[];"))
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS selected_batch_ids UUID[];"))
            # Ensure upi_id column exists on users table
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS upi_id VARCHAR;"))
            # Ensure course_id and batch_id columns exist on fee_payments table
            await conn.execute(text("ALTER TABLE fee_payments ADD COLUMN IF NOT EXISTS course_id UUID;"))
            await conn.execute(text("ALTER TABLE fee_payments ADD COLUMN IF NOT EXISTS batch_id UUID;"))
            print("Successfully ran startup database migrations!")
    except Exception as e:
        print(f"Error during startup database migrations: {e}")

@app.get("/")
def root():
    return {"message": "Welcome to the BuddyBloom API"}
