from fastapi import APIRouter
from app.api.api_v1.endpoints import (
    auth, users, students, batches, courses, 
    attendance, quizzes, notifications, 
    parent_dashboard, dashboard, homework
)

api_router = APIRouter()

# Explicitly register routers with prefixes
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(students.router, prefix="/students", tags=["students"])
api_router.include_router(batches.router, prefix="/batches", tags=["batches"])
api_router.include_router(courses.router, prefix="/courses", tags=["courses"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(quizzes.router, prefix="/quizzes", tags=["quizzes"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(parent_dashboard.router, prefix="/parents", tags=["parent-dashboard"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(homework.router, prefix="/homework", tags=["homework"])
