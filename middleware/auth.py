# app/middleware/auth.py
import os
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException
from jose import jwt
import httpx
from dotenv import load_dotenv

load_dotenv()

JWKS_URL = os.getenv("SUPABASE_JWKS_URL")
SUPABASE_AUD = os.getenv("SUPABASE_AUD")  # optional

# Simple in-memory JWKS cache
_jwks_cache = {"keys": None}

async def _fetch_jwks():
    if _jwks_cache["keys"] is None:
        async with httpx.AsyncClient() as c:
            r = await c.get(JWKS_URL, timeout=10.0)
            r.raise_for_status()
            _jwks_cache["keys"] = r.json()
    return _jwks_cache["keys"]

class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        
          # TEMPORARILY BYPASS AUTH FOR ALL ROUTES
        request.state.user_id = "test-user"
        request.state.tenant_id = "test-tenant"
        request.state.jwt_claims = {}
        return await call_next(request)
        
        auth = request.headers.get("authorization")
        if not auth or not auth.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        token = auth.split(" ", 1)[1].strip()

        # get JWKS and find key by kid
        jwks = await _fetch_jwks()
        try:
            kid = jwt.get_unverified_header(token).get("kid")
            matching = next((k for k in jwks["keys"] if k.get("kid") == kid), None)
            if not matching:
                raise HTTPException(status_code=401, detail="No matching JWK")
            claims = jwt.decode(
                token,
                matching,
                algorithms=[matching.get("alg", "RS256")],
                audience=SUPABASE_AUD if SUPABASE_AUD else None,
            )
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

        # attach user info to request state
        user_id = claims.get("sub")
        tenant_id = claims.get("tenant_id")
        if not user_id or not tenant_id:
            raise HTTPException(status_code=401, detail="Token missing required sub or tenant_id claim")

        request.state.user_id = user_id
        request.state.tenant_id = tenant_id
        request.state.jwt_claims = claims

        return await call_next(request)

# --------- Add this dependency for FastAPI endpoints ---------
async def auth_user(request: Request):
    """
    FastAPI dependency to get authenticated user ID from request state.
    """
    if not hasattr(request.state, "user_id") or not request.state.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return request.state.user_id
