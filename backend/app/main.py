"""
backend/app/main.py

Enterprise-grade async FastAPI application.

Key changes from prototype:
  - lifespan() is fully async: await wait_for_db(), async create_all().
  - All endpoints are async def with AsyncSession (no blocking I/O on event loop).
  - MinIO operations are wrapped in anyio.to_thread.run_sync() — the minio SDK is
    sync-only, but we keep it off the event loop via a thread executor.
  - GET /documents/ is Redis-cached (30 s TTL) to eliminate repeated Postgres
    lookups for the dashboard document list.
  - /chat/ uses the new async_query_rag() — no more 800ms embedding stall.
  - GET /health added for Kubernetes liveness and readiness probes.
  - Removed duplicate get_db() (now imported from app.database).
"""

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional

import anyio
import magic
import redis.asyncio as aioredis
from fastapi import FastAPI, File, HTTPException, Depends, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from minio import Minio
from minio.error import S3Error
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, auth, schemas
from app.database import async_engine, Base, get_db, wait_for_db
from app.docubrain_tasks import process_document_task
from app.rag import async_query_rag, async_delete_from_vector_store
from app.chat_router import router as chat_router

logger = logging.getLogger(__name__)

# ── Secure Local Storage Configuration ─────────────────────────────────────────
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Redis cache client (DB 1 — separate from Celery broker on DB 0) ───────────
_REDIS_CACHE_URL = os.getenv("REDIS_CACHE_URL") or os.getenv("REDIS_URL") or "redis://redis:6379/1"
_redis: Optional[aioredis.Redis] = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            _REDIS_CACHE_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis


def _docs_cache_key(user_id: int, target_user_id: Optional[int] = None) -> str:
    return f"docs:{user_id}:{target_user_id or ''}"


# ── Application lifespan ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    logger.info("🔄 DocuBrain starting up…")

    # 1. Wait for Postgres (async exponential backoff + SSL)
    try:
        await wait_for_db()
    except RuntimeError as exc:
        logger.critical("💀 Database startup probe FAILED: %s", exc)
        raise

    # 2. Create / migrate schema with the async engine
    try:
        async with async_engine.begin() as conn:
            logger.info("📐 Applying database schema (create_all)…")
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Schema applied.")
    except Exception as exc:
        logger.critical(
            "💀 Schema creation failed: %s: %s",
            exc.__class__.__name__, exc,
        )
        raise


    # 3. Local Uploads Directory initialized at startup module level.

    logger.info("🎉 DocuBrain backend is ready.")
    yield
    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("👋 Application shutting down…")
    await async_engine.dispose()
    if _redis is not None:
        await _redis.aclose()


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="DocuBrain API",
    version="2.0.0",
    description="Enterprise-grade AI Meeting Copilot — fully async backend.",
    lifespan=lifespan,
)

_FRONTEND_URL = (os.getenv("FRONTEND_URL") or "https://yourfrontend.vercel.app").rstrip("/")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        _FRONTEND_URL,
    ],
    # Allow ALL *.vercel.app subdomains (production + preview deploys)
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth")
app.include_router(chat_router)


# ── Local request schemas ──────────────────────────────────────────────────────
class LinkRequest(BaseModel):
    professional_email: str


class ClientListResponse(BaseModel):
    id: int
    email: str
    joined_at: datetime


class AdvancedChatRequest(BaseModel):
    message: str
    target_user_id: Optional[int] = None


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Kubernetes liveness / readiness probe — returns instantly."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/upload/")
async def upload_document(
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Security: magic-number check (file type forgery protection)
    file_header = await file.read(2048)
    await file.seek(0)
    real_file_type = magic.Magic(mime=True).from_buffer(file_header)
    if real_file_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Security Alert: File appears to be {real_file_type}, not a valid PDF.",
        )

    file_uuid  = str(uuid.uuid4())
    safe_filename = file.filename.replace(' ', '_').replace('/', '')
    local_path = os.path.join(UPLOAD_DIR, f"{file_uuid}_{safe_filename}")
    file_content = await file.read()

    # Upload to Local disk in a thread — never block the event loop with sync I/O
    await anyio.to_thread.run_sync(
        lambda: open(local_path, "wb").write(file_content)
    )

    # Save document record
    new_doc = models.Document(
        filename=file.filename,
        minio_path=local_path, # Repurposing to store the secure local path
        content_type=real_file_type,
        file_size=len(file_content),
        user_id=current_user.id,
    )
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)

    # Dispatch Celery background task for PDF embedding
    process_document_task.delay(new_doc.id)

    # Invalidate the document-list cache for this user
    try:
        await _get_redis().delete(_docs_cache_key(current_user.id))
    except Exception as exc:
        logger.warning("Redis cache invalidation failed (non-fatal): %s", exc)

    return {"message": "Upload successful", "uuid": file_uuid}


@app.get("/documents/", response_model=List[schemas.DocumentResponse])
async def read_documents(
    target_user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List documents for the authenticated user (or a linked client if professional).
    Response is Redis-cached for 30 s — dashboard refreshes skip Postgres entirely.
    """
    user_id_to_fetch = current_user.id

    if target_user_id is not None:
        if current_user.role != "professional":
            raise HTTPException(status_code=403, detail="Only professionals can view other users")

        # Verify the professional ↔ client link exists
        link_result = await db.execute(
            select(models.ProfessionalLink).where(
                models.ProfessionalLink.client_id == target_user_id,
                models.ProfessionalLink.professional_id == current_user.id,
            )
        )
        if not link_result.scalars().first():
            raise HTTPException(status_code=403, detail="Not linked to this client")

        user_id_to_fetch = target_user_id

    cache_key = _docs_cache_key(current_user.id, target_user_id)

    # 1. Try Redis cache (skip=0 / limit=100 is the default dashboard call)
    if skip == 0 and limit == 100:
        try:
            cached = await _get_redis().get(cache_key)
            if cached:
                logger.debug("CACHE HIT: %s", cache_key)
                return [schemas.DocumentResponse(**d) for d in json.loads(cached)]
        except Exception as exc:
            logger.warning("Redis read failed (non-fatal): %s", exc)

    # 2. Cache miss — query Postgres
    result = await db.execute(
        select(models.Document)
        .where(models.Document.user_id == user_id_to_fetch)
        .order_by(models.Document.upload_date.desc())
        .offset(skip)
        .limit(limit)
    )
    documents = result.scalars().all()

    # 3. Write to cache (only for the default pagination window)
    if skip == 0 and limit == 100:
        try:
            payload = json.dumps(
                [schemas.DocumentResponse.model_validate(d).model_dump(mode="json")
                 for d in documents]
            )
            await _get_redis().setex(cache_key, 30, payload)
        except Exception as exc:
            logger.warning("Redis write failed (non-fatal): %s", exc)

    return documents


@app.post("/chat/", response_model=schemas.ChatResponse)
async def chat_endpoint(
    request: AdvancedChatRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Legacy single-shot chat endpoint (no session persistence).
    Uses async_query_rag — Gemini embedding is async, ChromaDB in thread executor.
    """
    target_id = current_user.id

    if request.target_user_id:
        if current_user.role != "professional":
            raise HTTPException(status_code=403, detail="Unauthorized")

        link_result = await db.execute(
            select(models.ProfessionalLink).where(
                models.ProfessionalLink.client_id == request.target_user_id,
                models.ProfessionalLink.professional_id == current_user.id,
            )
        )
        if not link_result.scalars().first():
            raise HTTPException(status_code=403, detail="Not linked")

        target_id = request.target_user_id

    answer, sources = await async_query_rag(request.message, user_id=target_id)
    return {"response": answer, "sources": sources}


@app.post("/link/invite")
async def link_professional(
    link_req: LinkRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.User).where(
            models.User.email == link_req.professional_email,
            models.User.role == "professional",
        )
    )
    pro = result.scalars().first()
    if not pro:
        raise HTTPException(status_code=404, detail="Professional not found with that email")

    existing_result = await db.execute(
        select(models.ProfessionalLink).where(
            models.ProfessionalLink.client_id == current_user.id,
            models.ProfessionalLink.professional_id == pro.id,
        )
    )
    if existing_result.scalars().first():
        return {"message": "Already linked to this professional"}

    new_link = models.ProfessionalLink(client_id=current_user.id, professional_id=pro.id)
    db.add(new_link)
    await db.commit()
    return {"message": f"Successfully linked to {pro.email}"}


@app.get("/professional/clients", response_model=List[ClientListResponse])
async def get_clients(
    current_user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "professional":
        raise HTTPException(status_code=403, detail="Access denied")

    links_result = await db.execute(
        select(models.ProfessionalLink).where(
            models.ProfessionalLink.professional_id == current_user.id
        )
    )
    links = links_result.scalars().all()

    clients = []
    for link in links:
        user_result = await db.execute(
            select(models.User).where(models.User.id == link.client_id)
        )
        client_user = user_result.scalars().first()
        if client_user:
            clients.append(
                {"id": client_user.id, "email": client_user.email, "joined_at": link.created_at}
            )
    return clients


@app.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Document).where(
            models.Document.id == doc_id,
            models.Document.user_id == current_user.id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from Disk (sync SDK → thread executor)
    try:
        def _del_file():
            if os.path.exists(doc.minio_path):
                os.remove(doc.minio_path)
        await anyio.to_thread.run_sync(_del_file)
    except Exception as exc:
        logger.warning("⚠️ Disk delete warning: %s", exc)

    # Delete from ChromaDB (async wrapper — also uses thread executor)
    await async_delete_from_vector_store(doc_id)

    await db.delete(doc)
    await db.commit()

    # Invalidate document-list cache
    try:
        await _get_redis().delete(_docs_cache_key(current_user.id))
    except Exception as exc:
        logger.warning("Redis cache invalidation failed (non-fatal): %s", exc)

    return {"message": "Document and all associated data purged successfully"}