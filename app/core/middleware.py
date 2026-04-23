from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
from app.core.config import settings

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
            "/api/v1/users/",
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
