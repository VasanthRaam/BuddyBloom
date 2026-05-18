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

from app.core.middleware import SupabaseAuthMiddleware

# Set all CORS enabled origins
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

# Add JWT Authentication Middleware
app.add_middleware(SupabaseAuthMiddleware)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup_event():
    try:
        from app.db.database import engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS push_token VARCHAR;"))
            print("Successfully migrated push_token column on startup!")
    except Exception as e:
        print(f"Error migrating push_token: {e}")

@app.get("/")
def root():
    return {"message": "Welcome to the BuddyBloom API"}
