"""
app/services/chat_service.py

Chat session business logic: create, list, delete sessions; send messages; SSE streaming.
"""

import json
import logging
from typing import AsyncGenerator

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.redis_client import get_redis
from app.models import User
from app.repositories import chat_repository
from app.schemas.chat import ChatSessionResponse
from app.services import rag_service

logger = logging.getLogger(__name__)


def _sessions_cache_key(user_id: int) -> str:
    return f"chat_sessions:{user_id}"


async def create_session(db: AsyncSession, current_user: User) -> object:
    session = await chat_repository.create_session(db, current_user.id)
    try:
        await get_redis().delete(_sessions_cache_key(current_user.id))
    except Exception as exc:
        logger.warning("Cache invalidation failed (non-fatal): %s", exc)
    return session


async def list_sessions(db: AsyncSession, current_user: User) -> list:
    cache_key = _sessions_cache_key(current_user.id)
    try:
        cached = await get_redis().get(cache_key)
        if cached:
            return [ChatSessionResponse(**s) for s in json.loads(cached)]
    except Exception as exc:
        logger.warning("Redis read failed (non-fatal): %s", exc)

    sessions = await chat_repository.list_sessions(db, current_user.id)

    try:
        payload = json.dumps(
            [ChatSessionResponse.model_validate(s).model_dump(mode="json") for s in sessions]
        )
        await get_redis().setex(cache_key, 60, payload)
    except Exception as exc:
        logger.warning("Redis write failed (non-fatal): %s", exc)

    return sessions


async def delete_session(db: AsyncSession, session_id: int, current_user: User) -> None:
    session = await chat_repository.get_session(db, session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    await chat_repository.delete_session(db, session)
    try:
        await get_redis().delete(_sessions_cache_key(current_user.id))
    except Exception as exc:
        logger.warning("Cache invalidation failed (non-fatal): %s", exc)


async def get_messages(db: AsyncSession, session_id: int, current_user: User) -> list:
    session = await chat_repository.get_session(db, session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return await chat_repository.get_messages(db, session_id)


async def stream_response(
    db: AsyncSession,
    session_id: int,
    content: str,
    current_user: User,
) -> AsyncGenerator[str, None]:
    session = await chat_repository.get_session(db, session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    if session.title == "New Chat":
        session.title = content[:60].strip()
        db.add(session)
        await db.flush()

    user_msg = await chat_repository.add_message(db, session_id, "user", content)

    history_rows = await chat_repository.get_messages(db, session_id)
    history = [{"role": m.role, "content": m.content} for m in history_rows[-10:]]

    await db.commit()

    async def _generate() -> AsyncGenerator[str, None]:
        full_text = ""
        try:
            async for token in rag_service.stream_rag_response(content, history, current_user.id):
                if token.startswith("\n\n[SOURCES]"):
                    yield f"data: [SOURCES]{token.replace(chr(10)*2 + '[SOURCES]', '')}\n\n"
                else:
                    full_text += token
                    yield f"data: {token.replace(chr(10), chr(92) + 'n')}\n\n"

            await chat_repository.add_message(db, session_id, "assistant", full_text)
            await db.commit()
        except Exception as exc:
            logger.exception("SSE stream error for session %d: %s", session_id, exc)
            yield f"data: [ERROR]{exc}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return _generate()
