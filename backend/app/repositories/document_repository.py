from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document


async def get_by_user(
    db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100
) -> list[Document]:
    result = await db.execute(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.upload_date.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, doc_id: int) -> Document | None:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    return result.scalars().first()


async def create_document(
    db: AsyncSession,
    filename: str,
    minio_path: str,
    content_type: str,
    file_size: int,
    user_id: int,
) -> Document:
    doc = Document(
        filename=filename,
        minio_path=minio_path,
        content_type=content_type,
        file_size=file_size,
        user_id=user_id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def delete_document(db: AsyncSession, doc: Document) -> None:
    await db.delete(doc)
    await db.commit()
