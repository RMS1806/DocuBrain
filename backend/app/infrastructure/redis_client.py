"""
app/infrastructure/redis_client.py

Single shared async Redis client for the entire application.
Previously this was copy-pasted into main.py and chat_router.py separately.

The DB index is forced to /0 when only REDIS_URL is set (PaaS environments
share one Redis instance between Celery broker and app cache).
"""

import logging
from typing import Optional

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


def _normalise_redis_url(raw: str) -> str:
    """Append /0 DB index if no DB index is present in the URL."""
    if not any(raw.rstrip("/").endswith(f"/{i}") for i in range(16)):
        # Preserve query params (e.g. ?ssl_cert_reqs=CERT_NONE)
        if "?" in raw:
            base, qs = raw.split("?", 1)
            return f"{base.rstrip('/')}/0?{qs}"
        return f"{raw.rstrip('/')}/0"
    return raw


def get_redis() -> aioredis.Redis:
    """Return the singleton async Redis client, creating it on first call."""
    global _redis
    if _redis is None:
        url = _normalise_redis_url(settings.REDIS_URL)
        _redis = aioredis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
