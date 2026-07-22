"""Supabase Auth verification.

This project's Supabase instance uses asymmetric signing keys (ES256), not the
legacy shared HS256 secret — so verification fetches Supabase's public JWKS
rather than decoding against a stored secret. Works identically regardless of
which sign-in method (Google OAuth, email/password, etc.) issued the token,
since Supabase always issues its own JWT after any auth method.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import crud, get_async_session
from app.database.models import User

bearer_scheme = HTTPBearer(auto_error=False)

_jwks_client: Optional["jwt.PyJWKClient"] = None


def _get_jwks_client() -> "jwt.PyJWKClient":
    global _jwks_client
    if _jwks_client is None:
        if not settings.supabase_url:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Auth not configured on server")
        _jwks_client = jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
    return _jwks_client


@dataclass(frozen=True)
class AuthIdentity:
    sub: str
    email: Optional[str]


def _decode(token: str) -> AuthIdentity:
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing subject")
    return AuthIdentity(sub=sub, email=payload.get("email"))


async def get_current_user_optional(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[AuthIdentity]:
    """Decode-only, no DB I/O. A missing/invalid/expired token degrades to
    anonymous rather than raising — used on /chat, which must keep working
    for callers who never log in."""
    if creds is None:
        return None
    try:
        return _decode(creds.credentials)
    except HTTPException:
        return None


async def get_current_user_required(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_async_session),
) -> User:
    """Used only by the history endpoints, which have no meaningful
    anonymous/degraded mode — a bad token should fail loudly here."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    identity = _decode(creds.credentials)
    return await crud.get_or_create_user_by_identity(db, identity.sub, identity.email)
