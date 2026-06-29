"""
app/services/document_service.py

Document upload, listing, and deletion business logic.
S3 and vector store operations live here; the controller just calls these.
"""

import json
import logging
import uuid
import anyio

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.circuit_breaker import CircuitOpenError, s3_breaker
from app.infrastructure.redis_client import get_redis
from app.infrastructure.s3 import get_s3_client, upload_bytes_to_s3, delete_from_s3
from app.models import User
from app.repositories import document_repository
from app.schemas.document import DocumentResponse
from app.services import rag_service
from app.workers.document_worker import process_document_task

logger = logging.getLogger(__name__)


def _docs_cache_key(user_id: int) -> str:
    return f"docs:{user_id}"


async def upload_document(
    db: AsyncSession,
    filename: str,
    content: bytes,
    current_user: User,
) -> dict:
    file_uuid = str(uuid.uuid4())
    safe_name = filename.replace(" ", "_")
    s3_key = f"{file_uuid}_{safe_name}"

    try:
        await s3_breaker.call(
            lambda: anyio.to_thread.run_sync(
                lambda: upload_bytes_to_s3(get_s3_client(), settings.S3_BUCKET_NAME, s3_key, content, "application/pdf")
            )
        )
    except CircuitOpenError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    doc = await document_repository.create_document(
        db,
        filename=filename,
        minio_path=s3_key,
        content_type="application/pdf",
        file_size=len(content),
        user_id=current_user.id,
    )

    process_document_task.delay(doc.id)

    try:
        await get_redis().delete(_docs_cache_key(current_user.id))
    except Exception as exc:
        logger.warning("Cache invalidation failed (non-fatal): %s", exc)

    return {"message": "Upload successful", "uuid": file_uuid}



async def list_documents(
    db: AsyncSession,
    current_user: User,
    skip: int,
    limit: int,
) -> list[DocumentResponse]:
    cache_key = _docs_cache_key(current_user.id)

    if skip == 0 and limit == 100:
        try:
            cached = await get_redis().get(cache_key)
            if cached:
                return [DocumentResponse(**d) for d in json.loads(cached)]
        except Exception as exc:
            logger.warning("Redis read failed (non-fatal): %s", exc)

    docs = await document_repository.get_by_user(db, current_user.id, skip, limit)

    if skip == 0 and limit == 100:
        try:
            payload = json.dumps(
                [DocumentResponse.model_validate(d).model_dump(mode="json") for d in docs]
            )
            await get_redis().setex(cache_key, 30, payload)
        except Exception as exc:
            logger.warning("Redis write failed (non-fatal): %s", exc)

    return docs


async def delete_document(
    db: AsyncSession, doc_id: int, current_user: User
) -> dict:
    doc = await document_repository.get_by_id(db, doc_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        await anyio.to_thread.run_sync(
            lambda: delete_from_s3(get_s3_client(), settings.S3_BUCKET_NAME, doc.minio_path)
        )
    except Exception as exc:
        logger.warning("S3 delete warning: %s", exc)

    await rag_service.delete_from_vector_store_async(doc_id)
    await document_repository.delete_document(db, doc)

    try:
        await get_redis().delete(_docs_cache_key(current_user.id))
    except Exception as exc:
        logger.warning("Cache invalidation failed (non-fatal): %s", exc)

    return {"message": "Document and all associated data purged successfully"}
