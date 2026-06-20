from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
from app.core.config import settings
import time

class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exclude_paths: list[str] = None):
        super().__init__(app)
        # Paths that don't require authentication (like docs)
        self.exclude_paths = exclude_paths or [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            f"{settings.API_V1_STR}/openapi.json",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/courses-batches",
            "/api/v1/auth/test-token",
            "/api/v1/auth/google-sync",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/mobile-login-init",
            "/api/v1/auth/mobile-login-verify",
            "/api/v1/diagnostics/ping",
        ]

    async def dispatch(self, request: Request, call_next):
        # 1. Skip validation for excluded paths and OPTIONS requests
        path = request.url.path
        if request.method == "OPTIONS":
            return await call_next(request)

        is_excluded = any(
            (p == "/" and path == "/") or (p != "/" and path.startswith(p))
            for p in self.exclude_paths
        )
        
        if is_excluded:
            return await call_next(request)

        # 2. Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid Authorization header"}
            )

        token = auth_header.split(" ")[1]

        from app.core.security import verify_token
        # 3. Verify token
        try:
            payload = await verify_token(token)
            
            # 4. Attach user info to the request state
            request.state.user = {
                "id": payload.get("sub"),
                "role": payload.get("role"),
                "email": payload.get("email")
            }
            
        except Exception as e:
            # 5. Reject unauthorized requests
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": str(e) if hasattr(e, "detail") else "Invalid or expired token"}
            )

        # Proceed to the actual route
        return await call_next(request)


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


class ResponseTimingMiddleware(BaseHTTPMiddleware):
    """
    Measures server-side processing time for every request and injects it
    as the X-Response-Time header (in milliseconds). Use this from the
    frontend to separate network latency from server processing time:

        network_ms = total_round_trip_ms - parseInt(response.headers['x-response-time'])
    """
    async def dispatch(self, request: Request, call_next):
        t0 = time.monotonic()
        response = await call_next(request)
        elapsed_ms = round((time.monotonic() - t0) * 1000, 2)
        response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
        return response
