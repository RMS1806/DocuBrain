"""
backend/app/database.py

Enterprise-grade async SQLAlchemy 2.0 setup.

- Primary engine:  asyncpg + SQLAlchemy AsyncSession (FastAPI event loop)
- Fallback engine: psycopg2 + sync Session (Celery workers — separate OS process)
- Connection pool:  pool_size=50 / max_overflow=100, ready for PgBouncer in front
- Startup probe:   async exponential-backoff wait_for_db() using raw asyncpg
"""

import asyncio
import logging
import os

import asyncpg
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)

# ── Connection URLs ────────────────────────────────────────────────────────────
# FastAPI (async): asyncpg driver.
# Celery worker (sync): psycopg2 driver — imported via SYNC_DATABASE_URL or by
# stripping the +asyncpg suffix so one env var can serve both.

_RAW_DB_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://docubrain_user:secure_password@db/docubrain_db",
)

# Ensure FastAPI always gets the async URL regardless of which variant is set.
ASYNC_DATABASE_URL: str = _RAW_DB_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace("postgresql+psycopg2://", "postgresql+asyncpg://")

# Celery workers use the plain psycopg2 URL (separate env var or derived).
SYNC_DATABASE_URL: str = os.getenv(
    "SYNC_DATABASE_URL",
    _RAW_DB_URL.replace("postgresql+asyncpg://", "postgresql://"),
)

# ── Async Engine (FastAPI) ─────────────────────────────────────────────────────
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,       # Transparently recycle stale connections
    pool_size=50,             # Base pool — enough for 1,000 CCU behind PgBouncer
    max_overflow=100,         # Burst headroom; hard ceiling = 150 connections
    pool_recycle=300,         # Recycle every 5 min to prevent DNS/NAT drops
    pool_timeout=30,          # Raise if no connection available within 30 s
    echo=False,               # Set True only for SQL-level debugging
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # Avoids lazy-load errors after commit in async ctx
)

# ── Sync Engine (Celery Workers Only) ─────────────────────────────────────────
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,              # Workers have low concurrency — 5 is sufficient
    max_overflow=10,
    pool_recycle=300,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
)


# ── Declarative Base ───────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ── Async Startup Probe ────────────────────────────────────────────────────────
async def wait_for_db(max_retries: int = 10, initial_delay: float = 1.0) -> None:
    """
    Probe Postgres with a raw asyncpg connection (no SQLAlchemy overhead).
    Uses exponential backoff so the container waits gracefully instead of
    crashing on the first request when Postgres is still initialising.

    Args:
        max_retries:   Maximum connection attempts before aborting startup.
        initial_delay: Seconds before the first retry (doubles each attempt).
    """
    delay = initial_delay
    # asyncpg expects a plain DSN without the +asyncpg driver infix.
    probe_dsn = ASYNC_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    for attempt in range(1, max_retries + 1):
        try:
            conn = await asyncpg.connect(dsn=probe_dsn, timeout=10)
            await conn.fetchval("SELECT 1")
            await conn.close()
            logger.info("✅ Async database connection established (attempt %d).", attempt)
            return
        except (asyncpg.PostgresError, OSError, Exception) as exc:
            if attempt == max_retries:
                logger.critical(
                    "💀 Could not connect to Postgres after %d attempts.", max_retries
                )
                raise RuntimeError(
                    f"Database unreachable after {max_retries} attempts"
                ) from exc
            logger.warning(
                "⏳ DB not ready (attempt %d/%d). Retrying in %.1fs… (%s)",
                attempt,
                max_retries,
                delay,
                exc.__class__.__name__,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)  # Cap backoff at 30 s


# ── FastAPI Async Session Dependency ──────────────────────────────────────────
async def get_db() -> AsyncSession:
    """
    FastAPI dependency that yields a single AsyncSession per request.
    The session is automatically closed (and the connection returned to the
    pool) when the request finishes — even if an exception is raised.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise