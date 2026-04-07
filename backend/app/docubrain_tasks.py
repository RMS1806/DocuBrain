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
import pypdf
from sqlalchemy.exc import OperationalError

from app.database import SessionLocal   # sync session — correct for Celery
from app import models, rag

logger = get_task_logger(__name__)

# ── Celery app ─────────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL") or "redis://redis:6379/0"

# Handle DB index without breaking query parameters
if "REDIS_URL" in os.environ and "CELERY_BROKER_URL" not in os.environ:
    if not any(f"/{i}" in REDIS_URL for i in range(16)):
        if "?" in REDIS_URL:
            parts = REDIS_URL.split("?")
            REDIS_URL = f"{parts[0].rstrip('/')}/0?{parts[1]}"
        else:
            REDIS_URL = f"{REDIS_URL.rstrip('/')}/0"

# Fix Celery's strict rediss:// query parameter requirement
if REDIS_URL.startswith("rediss://") and "ssl_cert_reqs" not in REDIS_URL:
    sep = "&" if "?" in REDIS_URL else "?"
    REDIS_URL = f"{REDIS_URL}{sep}ssl_cert_reqs=CERT_NONE"

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

        # 3. Read PDF from Secure Local Storage
        logger.info("⬇️ Reading %s from Local Disk…", doc.minio_path)
        
        file_path = doc.minio_path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Missing file payload at {file_path}")
            
        with open(file_path, "rb") as f:
            pdf_data = f.read()

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

    except (FileNotFoundError, OperationalError, Exception) as exc:
        logger.exception("❌ CRITICAL FAILURE for doc_id=%d: %s", doc_id, exc)
        try:
            doc.status = "failed"
            db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        db.close()