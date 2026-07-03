from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.database import get_db
from app.api.deps import get_current_user
import time
import datetime

router = APIRouter()

# Tracks server startup time to detect cold starts
_SERVER_START_TIME = time.monotonic()
_SERVER_START_WALL = datetime.datetime.utcnow().isoformat() + "Z"


@router.get("/ping")
async def ping():
    """
    Public health-check endpoint (no auth required).
    Returns server uptime to help the frontend detect cold starts.
    Call this on app startup to warm up a sleeping free-tier server.
    """
    from app.core.config import settings
    db_part = settings.DATABASE_URL.split('//')[-1].split('@')[0]
    db_user = db_part.split(':')[0]
    db_host = settings.DATABASE_URL.split('@')[-1].split('/')[0]
    
    uptime_seconds = round(time.monotonic() - _SERVER_START_TIME, 1)
    return {
        "status": "ok",
        "server_time": datetime.datetime.utcnow().isoformat() + "Z",
        "server_started_at": _SERVER_START_WALL,
        "uptime_seconds": uptime_seconds,
        "cold_start": uptime_seconds < 30,
        "database_user": db_user,
        "database_host": db_host,
    }


@router.get("/latency")
async def check_latency(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Authenticated latency check. Measures:
    - Network latency (read from X-Response-Time header on the response)
    - Database round-trip latency (SELECT 1)

    Use this from the frontend console to diagnose slowness:
        apiClient.get('/diagnostics/latency').then(r => console.log('[Latency]', r.data));
    """
    t0 = time.monotonic()
    await db.execute(text("SELECT 1"))
    db_ms = round((time.monotonic() - t0) * 1000, 2)

    uptime_seconds = round(time.monotonic() - _SERVER_START_TIME, 1)

    return {
        "status": "ok",
        "db_latency_ms": db_ms,
        "server_uptime_seconds": uptime_seconds,
        "cold_start": uptime_seconds < 30,
        "server_time": datetime.datetime.utcnow().isoformat() + "Z",
        "user_role": current_user.get("role"),
        "note": (
            "Check X-Response-Time header for total server-side processing time. "
            "Network time = (client total time) - (X-Response-Time value)."
        ),
    }


@router.get("/test-push")
async def test_push(
    email: str = "vasanthraam89@gmail.com",
    db: AsyncSession = Depends(get_db)
):
    """
    Test push notification delivery directly via Expo API and return the response.
    """
    from app.db.models import User, UserPushToken
    from sqlalchemy.future import select
    import httpx

    # Find user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if not user:
        return {"status": "error", "message": f"User {email} not found"}

    # Find tokens
    result = await db.execute(select(UserPushToken.push_token).where(UserPushToken.user_id == user.id))
    tokens = result.scalars().all()
    if not tokens:
        return {"status": "error", "message": f"No push tokens found for {email} in DB"}

    # Send directly to Expo
    url = "https://exp.host/--/api/v2/push/send"
    messages = []
    for token in tokens:
        messages.append({
            "to": token,
            "title": "VHA EduTech Test 👤",
            "body": "This is a direct diagnostics push test!",
            "sound": "default",
            "priority": "high",
            "channelId": "default"
        })

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=messages)
            return {
                "status": "completed",
                "database_user_id": str(user.id),
                "device_tokens": tokens,
                "expo_status_code": response.status_code,
                "expo_response": response.json()
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
