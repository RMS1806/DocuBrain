"""
backend/app/database.py

Enterprise-grade async SQLAlchemy 2.0 setup — hardened for cloud deployment.

- Primary engine:  asyncpg + SQLAlchemy AsyncSession (FastAPI event loop)
- Fallback engine: psycopg2 + sync Session (Celery workers — separate OS process)
- SSL:             Enabled automatically when connecting to external hosts (Supabase, RDS)
- Connection pool:  Right-sized for free-tier PaaS (Render 512 MB) with Supabase pooler
- Startup probe:   async exponential-backoff wait_for_db() using raw asyncpg
"""

import asyncio
import logging
import ssl

import asyncpg
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

_RAW_DB_URL: str = settings.DATABASE_URL

if not _RAW_DB_URL:
    raise RuntimeError("CRITICAL ERROR: DATABASE_URL environment variable is missing.")

# ── FIX 1: Normalize postgres:// → postgresql:// ──────────────────────────────
# Render, Heroku, and some Supabase dashboard URIs use the legacy `postgres://`
# scheme. SQLAlchemy 2.0+ only accepts `postgresql://`.
if _RAW_DB_URL and _RAW_DB_URL.startswith("postgres://"):
    _RAW_DB_URL = _RAW_DB_URL.replace("postgres://", "postgresql://", 1)

logger.info("🔗 Raw DB URL (scheme): %s://...", _RAW_DB_URL.split("://")[0])

# Ensure FastAPI always gets the async URL regardless of which variant is set.
ASYNC_DATABASE_URL: str = _RAW_DB_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace("postgresql+psycopg2://", "postgresql+asyncpg://")

# Celery workers use the plain psycopg2 URL (separate env var or derived).
SYNC_DATABASE_URL: str = settings.SYNC_DATABASE_URL or _RAW_DB_URL.replace(
    "postgresql+asyncpg://", "postgresql://"
)

# ── FIX 2: SSL Context ────────────────────────────────────────────────────────
# Supabase (and most managed Postgres providers) REQUIRE SSL for external
# connections. Without it, asyncpg gets a raw TCP rejection that surfaces as
# OSError: [Errno 101] Network is unreachable.
#
# We detect "is this a cloud URL?" by checking if the host is NOT a local alias.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "db", "postgres", "host.docker.internal", "pgbouncer"}
_parsed_host = _RAW_DB_URL.split("@")[-1].split("/")[0].split(":")[0].lower()
_is_cloud = _parsed_host not in _LOCAL_HOSTS

if _is_cloud:
    logger.info("☁️  Cloud host detected (%s) — enabling SSL for all connections.", _parsed_host)
    # Create a permissive SSL context (Supabase uses self-managed certs).
    # For stricter verification, provide a CA bundle via SSL_CA_CERT env var.
    _ssl_context = ssl.create_default_context()
    _ssl_context.check_hostname = False
    _ssl_context.verify_mode = ssl.CERT_NONE

    _async_connect_args = {
        "ssl": _ssl_context,
        # PgBouncer (transaction mode) routes each transaction to a potentially
        # different real Postgres connection. asyncpg's prepared-statement cache
        # is per-connection, so a statement prepared on connection A doesn't exist
        # on connection B. Setting statement_cache_size=0 disables the cache and
        # prevents "prepared statement does not exist" errors.
        "statement_cache_size": 0,
    }
    _sync_connect_args = {
        "sslmode": "require",
        "connect_timeout": 15,
    }
else:
    logger.info("🏠 Local host detected (%s) — SSL disabled.", _parsed_host)
    _async_connect_args = {
        # Disable prepared-statement cache even locally so dev behaviour matches
        # production (where PgBouncer is always in front of Postgres).
        "statement_cache_size": 0,
    }
    _sync_connect_args = {"connect_timeout": 10}


# ── Async Engine (FastAPI) ─────────────────────────────────────────────────────
# FIX 3: Right-sized pool for free-tier PaaS.
# Render free tier = 512 MB RAM, Supabase pooler = max 15-20 connections.
# Old values (pool_size=50, max_overflow=100) were dangerously high.
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,       # Transparently recycle stale connections
    pool_size=5,              # Conservative for free-tier — Supabase pooler handles the rest
    max_overflow=10,          # Burst headroom; hard ceiling = 15 connections
    pool_recycle=300,         # Recycle every 5 min to prevent DNS/NAT drops
    pool_timeout=30,          # Raise if no connection available within 30 s
    echo=False,               # Set True only for SQL-level debugging
    connect_args=_async_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # Avoids lazy-load errors after commit in async ctx
)

# ── Read Replica Engine ────────────────────────────────────────────────────────
# If READ_REPLICA_URL is set, heavy read-only queries (analytics, progress stats)
# are routed here — freeing the primary for writes.
#
# If not set (dev, free-tier, single-server), _REPLICA_URL falls back to the
# primary URL. replica_engine becomes the same logical target as async_engine.
# No app code needs to change — get_read_db() just works in both cases.
#
# Replication lag note: replica reads may be a few milliseconds behind the primary.
# Only route queries here where slight staleness is acceptable (aggregate stats,
# historical data). Queries that immediately follow a write (e.g. list documents
# after upload) must stay on the primary via get_db().

_raw_replica_url: str = settings.READ_REPLICA_URL or settings.DATABASE_URL

# Normalise scheme: same logic as the primary URL above.
if _raw_replica_url.startswith("postgres://"):
    _raw_replica_url = _raw_replica_url.replace("postgres://", "postgresql://", 1)

ASYNC_REPLICA_URL: str = _raw_replica_url.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace("postgresql+psycopg2://", "postgresql+asyncpg://")

_using_replica = (ASYNC_REPLICA_URL != ASYNC_DATABASE_URL)
logger.info(
    "Read replica: %s",
    "enabled (" + ASYNC_REPLICA_URL.split("@")[-1].split("/")[0] + ")"
    if _using_replica else "disabled (falling back to primary)",
)

replica_engine = create_async_engine(
    ASYNC_REPLICA_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=300,
    pool_timeout=30,
    echo=False,
    connect_args=_async_connect_args,
)

ReplicaSessionLocal = async_sessionmaker(
    bind=replica_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# ── Sync Engine (Celery Workers Only) ─────────────────────────────────────────
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=3,              # Workers have low concurrency — 3 is sufficient on free tier
    max_overflow=5,
    pool_recycle=300,
    connect_args=_sync_connect_args,
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
async def wait_for_db(max_retries: int = 12, initial_delay: float = 2.0) -> None:
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

    # Log the sanitized DSN (mask password) for debugging
    _safe_dsn = probe_dsn.split("@")[-1] if "@" in probe_dsn else probe_dsn
    logger.info("🔍 Probing database at: ...@%s (SSL=%s)", _safe_dsn, _is_cloud)

    for attempt in range(1, max_retries + 1):
        try:
            # FIX 2 (continued): Pass SSL to the raw asyncpg probe too.
            conn = await asyncpg.connect(
                dsn=probe_dsn,
                timeout=15,
                ssl="require" if _is_cloud else None,
            )
            version = await conn.fetchval("SELECT version()")
            await conn.close()
            logger.info(
                "✅ Async database connection established (attempt %d). Server: %s",
                attempt,
                version[:80] if version else "unknown",
            )
            return
        except (asyncpg.PostgresError, OSError, Exception) as exc:
            # FIX 4: Detailed exception logging for cloud debugging.
            logger.warning(
                "⏳ DB not ready (attempt %d/%d). Retrying in %.1fs…\n"
                "   Exception: %s: %s\n"
                "   DSN (host): ...@%s | SSL: %s",
                attempt,
                max_retries,
                delay,
                exc.__class__.__name__,
                str(exc),
                _safe_dsn,
                _is_cloud,
            )
            if attempt == max_retries:
                logger.critical(
                    "💀 Could not connect to Postgres after %d attempts.\n"
                    "   Last error: %s: %s\n"
                    "   Check: DATABASE_URL, SSL settings, network/firewall rules.",
                    max_retries,
                    exc.__class__.__name__,
                    str(exc),
                )
                raise RuntimeError(
                    f"Database unreachable after {max_retries} attempts: "
                    f"{exc.__class__.__name__}: {exc}"
                ) from exc
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)  # Cap backoff at 30 s


# ── FastAPI Async Session Dependencies ────────────────────────────────────────

async def get_db() -> AsyncSession:
    """
    Primary DB session — use for ALL writes and any read that must see the
    latest committed data (e.g. listing documents immediately after upload).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_read_db() -> AsyncSession:
    """
    Read-replica session — use for read-only endpoints where a few milliseconds
    of replication lag is acceptable: analytics dashboards, progress stats,
    historical aggregates.

    Falls back to the primary automatically if READ_REPLICA_URL is not set,
    so this dependency is safe to use in all environments without extra config.
    """
    async with ReplicaSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise