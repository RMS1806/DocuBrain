"""
app/services/auth_service.py

Authentication business logic: registration, login, token refresh, logout.
The HTTP layer (api/v1/auth.py) calls these functions.

Two-token pattern:
  - Access token  : 15-min JWT, returned in response body
  - Refresh token : 7-day random UUID stored in Redis, sent via httpOnly cookie
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.infrastructure.redis_client import get_redis
from app.repositories import user_repository

_REFRESH_PREFIX = "refresh_token:"
_REFRESH_TTL = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # seconds


def _make_claims(user) -> dict:
    return {"sub": user.email, "user_id": user.id}


async def _store_refresh_token(user_id: int, token: str) -> None:
    await get_redis().setex(f"{_REFRESH_PREFIX}{token}", _REFRESH_TTL, str(user_id))


async def _pop_refresh_token(token: str) -> int | None:
    """Atomically read + delete (rotation). Returns user_id or None if not found."""
    key = f"{_REFRESH_PREFIX}{token}"
    redis = get_redis()
    value = await redis.get(key)
    if value is None:
        return None
    await redis.delete(key)
    return int(value)


async def register_user(
    db: AsyncSession, email: str, password: str
) -> tuple[str, str, int]:
    existing = await user_repository.get_by_email(db, email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = hash_password(password)
    user = await user_repository.create_user(db, email, hashed)

    access_token = create_access_token(_make_claims(user))
    refresh_token = create_refresh_token()
    await _store_refresh_token(user.id, refresh_token)

    return access_token, refresh_token, user.id


async def login_user(
    db: AsyncSession, email: str, password: str
) -> tuple[str, str, int]:
    user = await user_repository.get_by_email(db, email)
    if not user or not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(_make_claims(user))
    refresh_token = create_refresh_token()
    await _store_refresh_token(user.id, refresh_token)

    return access_token, refresh_token, user.id


async def refresh_tokens(
    db: AsyncSession, old_refresh_token: str
) -> tuple[str, str, str]:
    """
    Validate the old refresh token, rotate it, and return a fresh pair.
    Token rotation: old token is deleted from Redis before the new one is written.
    If the same old token is used twice, the second call gets a 401 — theft detected.
    """
    user_id = await _pop_refresh_token(old_refresh_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or has already been used",
        )

    user = await user_repository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access_token = create_access_token(_make_claims(user))
    new_refresh_token = create_refresh_token()
    await _store_refresh_token(user.id, new_refresh_token)

    return access_token, new_refresh_token


async def logout(refresh_token: str) -> None:
    """Delete the refresh token from Redis. Immediate revocation — no expiry wait."""
    key = f"{_REFRESH_PREFIX}{refresh_token}"
    await get_redis().delete(key)
