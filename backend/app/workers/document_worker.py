"""
app/workers/document_worker.py

Celery background worker for PDF processing.
Purposefully synchronous — Celery runs in its own OS process with no event loop.

Connection discipline: each DB interaction uses its own short-lived session that
is closed before any slow I/O (S3 download, Gemini API, Pinecone upsert) begins.
This prevents the sync psycopg2 connection from timing out while waiting on
external APIs that can take 30-90 seconds for large PDFs.
"""

import io
import json
import logging

import time

import pypdf
import redis as redis_sync
from celery import Celery
from celery.utils.log import get_task_logger
from google.api_core.exceptions import ResourceExhausted
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.database import SessionLocal
from app import models
from app.services.rag_service import add_to_vector_store
from app.infrastructure.s3 import get_s3_client, download_bytes_from_s3

logger = get_task_logger(__name__)


def _build_broker_url() -> str:
    url = settings.REDIS_URL
    if not any(url.rstrip("/").endswith(f"/{i}") for i in range(16)):
        if "?" in url:
            base, qs = url.split("?", 1)
            url = f"{base.rstrip('/')}/0?{qs}"
        else:
            url = f"{url.rstrip('/')}/0"
    if url.startswith("rediss://") and "ssl_cert_reqs" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}ssl_cert_reqs=CERT_NONE"
    return url


BROKER_URL = _build_broker_url()

celery_app = Celery("docubrain", broker=BROKER_URL, backend=BROKER_URL)
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=20,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
)


def _notify_document_ready(user_id: int, doc_id: int, filename: str) -> None:
    """
    Publish a real-time notification to the FastAPI WebSocket layer via Redis Pub/Sub.
    Uses a throwaway sync Redis connection — the worker has no event loop.
    Failure is non-fatal: the document is already saved; the user just won't get a push.
    """
    try:
        r = redis_sync.from_url(settings.REDIS_URL, decode_responses=True)
        payload = json.dumps({
            "type": "document.ready",
            "document_id": doc_id,
            "filename": filename,
            "status": "ready",
        })
        r.publish(f"doc:ready:{user_id}", payload)
        r.close()
    except Exception as exc:
        logger.warning("Failed to publish doc:ready notification: %s", exc)


def _set_doc_status(doc_id: int, status: str, summary: str | None = None) -> None:
    """Open a fresh session, update status, close. Never held across slow I/O."""
    db = SessionLocal()
    try:
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if doc:
            doc.status = status
            if summary is not None:
                doc.summary = summary
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def process_document_task(self, doc_id: int):
    """Download PDF from S3, extract text, chunk+embed via Gemini, upsert to Pinecone."""
    logger.info("Processing document ID %d", doc_id)

    # ── Step 1: Read doc metadata, mark processing ──────────────────────────
    # Session opened and closed before any slow I/O begins.
    db = SessionLocal()
    try:
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if not doc:
            logger.error("Document ID %d not found.", doc_id)
            return
        minio_path = doc.minio_path
        filename   = doc.filename
        user_id    = doc.user_id
        doc.status = "processing"
        db.commit()
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()  # Connection returned to pool before any external I/O

    # ── Step 2: Slow I/O — no DB connection held ────────────────────────────
    try:
        pdf_data = download_bytes_from_s3(
            get_s3_client(), settings.S3_BUCKET_NAME, minio_path
        )

        pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_data))
        full_text = "".join(
            page.extract_text() or "" for page in pdf_reader.pages
        )

        add_to_vector_store(
            text=full_text,
            metadata={"source": filename, "doc_id": doc_id, "user_id": user_id},
        )

    except ResourceExhausted as exc:
        # Gemini quota hit — back off 60 s so the per-minute window resets
        logger.warning("Gemini quota exceeded for doc %d — retrying in 60s", doc_id)
        try:
            _set_doc_status(doc_id, "processing")   # keep visible as processing, not failed
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)

    except Exception as exc:
        logger.exception("Failed processing doc_id=%d: %s", doc_id, exc)
        try:
            _set_doc_status(doc_id, "failed")
        except Exception:
            pass
        raise self.retry(exc=exc)

    # ── Step 3: Mark ready — fresh session ──────────────────────────────────
    try:
        summary = full_text[:200].strip() + "…" if len(full_text) > 200 else full_text
        _set_doc_status(doc_id, "ready", summary)
        logger.info("Finished processing document %s", filename)
    except Exception as exc:
        logger.exception("Failed to mark doc %d as ready: %s", doc_id, exc)
        raise self.retry(exc=exc)

    # ── Step 4: Push WebSocket notification ─────────────────────────────────
    _notify_document_ready(user_id, doc_id, filename)
