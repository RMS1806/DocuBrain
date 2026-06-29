"""
app/core/security.py

JWT creation, password hashing, and refresh token generation.
Previously lived in app/utils.py. Renamed to 'security' to reflect purpose.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token() -> str:
    """
    Generate a cryptographically secure random refresh token (512 bits).
    This is NOT a JWT — it's a random lookup key stored in Redis.
    Using a random secret (not a JWT) is what makes revocation possible.
    """
    return secrets.token_urlsafe(64)
