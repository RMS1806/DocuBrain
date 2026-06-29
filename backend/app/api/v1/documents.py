import magic
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.dependencies import get_current_user
from app.core.rate_limiter import upload_rate_limit
from app.database import get_db
from app.models import User
from app.schemas.document import DocumentResponse
from app.services import audit_service, document_service

router = APIRouter(tags=["documents"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_FILENAME_LENGTH = 255


@router.post("/upload/")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(upload_rate_limit),  # 10 uploads/hr, checked before any I/O
):
    if not file.filename or len(file.filename) > MAX_FILENAME_LENGTH:
        raise HTTPException(status_code=400, detail="Invalid or missing filename (max 255 chars)")

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds the 20 MB limit")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    real_type = magic.Magic(mime=True).from_buffer(content[:2048])
    if real_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Security Alert: File appears to be '{real_type}', not a PDF.",
        )

    result = await document_service.upload_document(db, file.filename, content, current_user)
    background_tasks.add_task(
        audit_service.log,
        user_id=current_user.id,
        action=audit_service.Action.DOCUMENT_UPLOAD,
        metadata={"filename": file.filename, "size_bytes": len(content)},
        ip_address=request.client.host if request.client else None,
    )
    return result


@router.get("/documents/", response_model=List[DocumentResponse])
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.list_documents(db, current_user, skip, limit)


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await document_service.delete_document(db, doc_id, current_user)
    background_tasks.add_task(
        audit_service.log,
        user_id=current_user.id,
        action=audit_service.Action.DOCUMENT_DELETE,
        resource_id=doc_id,
        ip_address=request.client.host if request.client else None,
    )
    return result
