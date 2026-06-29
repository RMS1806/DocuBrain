"""
app/core/rate_limiter.py

Fixed-window Redis rate limiting, implemented as FastAPI dependency factories.

How it works:
  Each user gets a Redis counter keyed by (user_id, time_window).
  The window is the current Unix timestamp integer-divided by window_seconds.
  INCR is atomic in Redis, so concurrent requests never race past the limit.
  TTL is set to 2x the window so Redis auto-cleans old keys.

Usage:
  general_rate_limit and upload_rate_limit are pre-built Depends()-ready callables.
  Add them to include_router(dependencies=[...]) for whole-router coverage,
  or as a parameter dependency on individual endpoints.
"""

import time

from fastapi import Depends, HTTPException, status

from app.config import settings
from app.core.dependencies import get_current_user
from app.infrastructure.redis_client import get_redis
from app.models import User


def rate_limit(limit: int, window_seconds: int):
    """
    Returns a FastAPI dependency that enforces per-user rate limiting.

    limit          : max allowed requests inside the window
    window_seconds : window size (60 = per minute, 3600 = per hour)

    Redis key format: rate:{window_seconds}:{user_id}:{bucket}
    where bucket = floor(unix_timestamp / window_seconds)
    """

    async def _check(current_user: User = Depends(get_current_user)) -> None:
        # Rate limiting is a production guard only — skip in dev/test so load
        # tests and local development aren't capped by the Redis counter.
        if settings.ENVIRONMENT != "production":
            return

        bucket = int(time.time()) // window_seconds
        key = f"rate:{window_seconds}:{current_user.id}:{bucket}"
        redis = get_redis()

        count = await redis.incr(key)
        if count == 1:
            # First hit in this window — arm the TTL so the key self-destructs.
            # 2× window guarantees the key outlives the window it was created in.
            await redis.expire(key, window_seconds * 2)

        if count > limit:
            unit = "minute" if window_seconds == 60 else f"{window_seconds}s"
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {limit} requests per {unit}.",
                headers={"Retry-After": str(window_seconds)},
            )

    return _check


# ── Pre-built limiters ────────────────────────────────────────────────────────

general_rate_limit = rate_limit(100, 60)    # 100 req / min  — all protected routes
upload_rate_limit = rate_limit(10, 3600)    # 10 uploads / hr — upload endpoint only
