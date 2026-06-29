"""
app/main.py

FastAPI application factory.
This file's only job: create the app, attach middleware, register routers.
All business logic has moved into api/v1/, services/, repositories/.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import settings
from app.core.logging import configure_logging
from app.core.middleware import CorrelationIDMiddleware
from app.core.rate_limiter import general_rate_limit
from app.database import async_engine, wait_for_db
from app.infrastructure.redis_client import close_redis
from app.infrastructure.s3 import ensure_bucket, get_s3_client
from app.api.v1 import auth, documents, chat, network, quiz, progress, ws, analytics

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    settings.validate()
    logger.info("DocuBrain starting up…")

    await wait_for_db()
    # Schema is managed by Alembic — entrypoint.sh runs "alembic upgrade head"
    # before uvicorn starts, so the DB is always up to date by the time we get here.

    ensure_bucket(get_s3_client(), settings.S3_BUCKET_NAME)
    logger.info("MinIO bucket ready: %s", settings.S3_BUCKET_NAME)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down…")
    await async_engine.dispose()
    await close_redis()


app = FastAPI(
    title="DocuBrain API",
    version="2.0.0",
    description="AI Study Workspace — enterprise async backend.",
    lifespan=lifespan,
)

# Middleware executes in reverse registration order (last added = outermost).
# CorrelationIDMiddleware is added last so it runs first on every request —
# the UUID must exist before CORS headers or rate limiting touch the request.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.add_middleware(CorrelationIDMiddleware)

app.include_router(auth.router)
# general_rate_limit applies 100 req/min per authenticated user to every route on these routers.
# Auth router is excluded — users aren't authenticated there yet (login/register are open).
app.include_router(documents.router, dependencies=[Depends(general_rate_limit)])
app.include_router(chat.router, dependencies=[Depends(general_rate_limit)])
app.include_router(network.router, dependencies=[Depends(general_rate_limit)])
app.include_router(quiz.router, dependencies=[Depends(general_rate_limit)])
app.include_router(progress.router, dependencies=[Depends(general_rate_limit)])
app.include_router(analytics.router, dependencies=[Depends(general_rate_limit)])
# WebSocket router: no rate limit dependency — WS handshakes don't carry Bearer tokens
app.include_router(ws.router)


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    # No auth — Prometheus scrapes this from inside the infra network, not the public internet.
    # include_in_schema=False hides it from the Swagger UI.
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
