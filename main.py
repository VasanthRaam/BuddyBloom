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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Add JWT Authentication Middleware
app.add_middleware(SupabaseAuthMiddleware)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to the BuddyBloom API"}
