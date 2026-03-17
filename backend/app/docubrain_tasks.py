"""
backend/app/docubrain_tasks.py

Celery worker — purposefully synchronous.

The worker runs in its own OS process, independent of the FastAPI event loop.
Putting async code in a Celery task requires a dedicated event loop which
causes subtle threading bugs with SQLAlchemy and ChromaDB. Best practice:
keep the worker sync, keep FastAPI async.

Changes from prototype:
  - Imports sync SessionLocal from database (psycopg2 engine — unchanged).
  - rag.add_text_to_vector_store() now uses Gemini Embeddings API (sync variant)
    instead of HuggingFace sentence-transformers. No heavy model to load = faster
    worker startup and zero CPU-bound stall on the API container.
"""

import io
import os
import time

from celery import Celery
from celery.utils.log import get_task_logger
from minio import Minio
from minio.error import S3Error
import pypdf
from sqlalchemy.exc import OperationalError

from app.database import SessionLocal   # sync session — correct for Celery
from app import models, rag

logger = get_task_logger(__name__)

# ── Celery app ─────────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "docubrain_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=20,
    task_acks_late=True,            # Only ack after success
    worker_prefetch_multiplier=1,   # Fair dispatch — no pre-fetch
    task_track_started=True,
)

# ── MinIO client ───────────────────────────────────────────────────────────────
minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "minio:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=False,
)
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "docubrain-uploads")


def _get_minio_object_with_retry(
    bucket: str,
    path: str,
    max_retries: int = 5,
    initial_delay: float = 2.0,
) -> bytes:
    """Download an object from MinIO, retrying on transient failures."""
    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            response = minio_client.get_object(bucket, path)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except (S3Error, Exception) as exc:
            if attempt == max_retries:
                raise
            logger.warning(
                "⏳ MinIO fetch failed (attempt %d/%d). Retrying in %.1fs… (%s)",
                attempt, max_retries, delay, exc,
            )
            time.sleep(delay)
            delay = min(delay * 2, 30)


# ── Task ───────────────────────────────────────────────────────────────────────
@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def process_document_task(self, doc_id: int):
    """
    Background task: download the PDF from MinIO, extract text,
    chunk + embed via Gemini API (sync), upsert into ChromaDB,
    and update the document status in Postgres.
    """
    logger.info("🧠 NEURAL CORE: Processing Document ID %d…", doc_id)

    db = SessionLocal()
    try:
        # 1. Fetch document record
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if not doc:
            logger.error("❌ Document ID %d not found.", doc_id)
            return "Failed: document not found"

        # 2. Mark as processing
        doc.status = "processing"
        db.commit()

        # 3. Download PDF from MinIO
        logger.info("⬇️ Downloading %s from Object Storage…", doc.minio_path)
        pdf_data = _get_minio_object_with_retry(MINIO_BUCKET, doc.minio_path)

        # 4. Extract text
        logger.info("📖 Extracting text from PDF…")
        pdf_reader = pypdf.PdfReader(io.BytesIO(pdf_data))
        full_text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n"

        # 5. Embed & upsert into ChromaDB via Gemini Embeddings (sync)
        #    rag.add_text_to_vector_store() chunks the text and calls
        #    get_gemini_embeddings_sync() — no PyTorch, no GPU, no CPU stall.
        logger.info(
            "💾 Chunking & embedding Doc ID %d for User ID %d via Gemini…",
            doc_id, doc.user_id,
        )
        rag.add_text_to_vector_store(
            text=full_text,
            metadata={
                "source": doc.filename,
                "doc_id": doc_id,
                "user_id": doc.user_id,
            },
        )

        # 6. Mark as completed
        doc.status  = "completed"
        doc.summary = full_text[:100] + "…"
        db.commit()

        logger.info("✅ FINISHED: %s has been vectorised.", doc.filename)
        return "Success"

    except (S3Error, OperationalError, Exception) as exc:
        logger.exception("❌ CRITICAL FAILURE for doc_id=%d: %s", doc_id, exc)
        try:
            doc.status = "failed"
            db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        db.close()