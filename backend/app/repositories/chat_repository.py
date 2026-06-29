from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatSession, ChatMessage


async def get_session(
    db: AsyncSession, session_id: int, user_id: int
) -> ChatSession | None:
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
    )
    return result.scalars().first()


async def list_sessions(db: AsyncSession, user_id: int) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.desc())
    )
    return list(result.scalars().all())


async def create_session(db: AsyncSession, user_id: int) -> ChatSession:
    session = ChatSession(user_id=user_id, title="New Chat")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def delete_session(db: AsyncSession, session: ChatSession) -> None:
    await db.delete(session)
    await db.commit()


async def get_messages(
    db: AsyncSession, session_id: int
) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return list(result.scalars().all())


async def add_message(
    db: AsyncSession, session_id: int, role: str, content: str
) -> ChatMessage:
    msg = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(msg)
    await db.flush()
    return msg
