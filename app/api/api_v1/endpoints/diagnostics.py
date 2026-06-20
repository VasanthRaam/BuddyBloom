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
    uptime_seconds = round(time.monotonic() - _SERVER_START_TIME, 1)
    return {
        "status": "ok",
        "server_time": datetime.datetime.utcnow().isoformat() + "Z",
        "server_started_at": _SERVER_START_WALL,
        "uptime_seconds": uptime_seconds,
        # Flag a likely cold start: server started less than 30 seconds ago
        "cold_start": uptime_seconds < 30,
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
