from jose import jwt, JWTError
from fastapi import HTTPException, status
import httpx
from app.core.config import settings
from datetime import datetime, timezone, timedelta

# Cache for the Supabase public key
_public_key = None

async def get_supabase_public_key():
    global _public_key
    if _public_key is None:
        try:
            # Supabase provides public keys via JWKS
            jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
                _public_key = response.json()
        except Exception as e:
            print(f"Error fetching Supabase public key: {e}")
            return None
    return _public_key

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=365)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

async def verify_token(token: str) -> dict:
    try:
        # First, try to decode without verification to see the algorithm
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")

        if alg == "HS256":
            # Standard symmetric verification
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False, "verify_exp": False}
            )
        else:
            # Asymmetric verification (ES256 / RS256) using Public Key
            jwks = await get_supabase_public_key()
            if not jwks:
                raise JWTError("Could not fetch public key")
                
            payload = jwt.decode(
                token,
                jwks,
                algorithms=[alg],
                options={"verify_aud": False, "verify_exp": False}
            )
            
        # Custom expiration check: extend token validity by 30 days
        exp = payload.get("exp")
        if exp:
            exp_date = datetime.fromtimestamp(exp, tz=timezone.utc)
            if datetime.now(timezone.utc) > exp_date + timedelta(days=30):
                raise JWTError("Signature has expired beyond the extended 30-day allowance.")
                
        return payload
            
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
