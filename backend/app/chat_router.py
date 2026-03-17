"""
backend/app/chat_router.py

Async persistent chat-session endpoints with Redis caching and SSE streaming.

Enterprise additions:
  - All endpoints are async def with AsyncSession (no event-loop blocking).
  - GET /chat/sessions is Redis-cached (60 s TTL) to avoid repeated Postgres
    round-trips for the sidebar list render.
  - POST /chat/sessions/{id}/stream streams LLM tokens as Server-Sent Events,
    enabling true sub-200 ms Time-To-First-Token for the frontend.
"""

import json
import logging
import os
from typing import AsyncGenerator, List, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas, auth
from app.database import get_db
from app.rag import async_query_rag_with_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# ── Redis cache client ─────────────────────────────────────────────────────────
# DB index 1 is dedicated to app-level caching (not the Celery broker on DB 0).
_REDIS_CACHE_URL = os.getenv("REDIS_CACHE_URL", "redis://redis:6379/1")
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


def _sessions_cache_key(user_id: int) -> str:
    return f"chat_sessions:{user_id}"


# ── DB helper ─────────────────────────────────────────────────────────────────
async def _own_session(
    session_id: int, user: models.User, db: AsyncSession
) -> models.ChatSession:
    """Fetch *session_id* and verify it belongs to *user*."""
    result = await db.execute(
        select(models.ChatSession).where(
            models.ChatSession.id == session_id,
            models.ChatSession.user_id == user.id,
        )
    )
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=schemas.ChatSessionResponse, status_code=201)
async def create_session(
    current_user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new empty chat session for the current user."""
    session = models.ChatSession(user_id=current_user.id, title="New Chat")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.info("Created chat session %d for user %d", session.id, current_user.id)

    # Invalidate the session-list cache for this user.
    try:
        await _get_redis().delete(_sessions_cache_key(current_user.id))
    except Exception as exc:
        logger.warning("Redis cache invalidation failed (non-fatal): %s", exc)

    return session


@router.get("/sessions", response_model=List[schemas.ChatSessionResponse])
async def list_sessions(
    current_user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all sessions for the current user, newest first.
    Result is cached in Redis for 60 s — subsequent sidebar renders are ~10 ms.
    """
    cache_key = _sessions_cache_key(current_user.id)

    # 1. Try cache
    try:
        cached = await _get_redis().get(cache_key)
        if cached:
            logger.debug("CACHE HIT: %s", cache_key)
            # Deserialise and return as Pydantic models
            return [schemas.ChatSessionResponse(**s) for s in json.loads(cached)]
    except Exception as exc:
        logger.warning("Redis read failed (non-fatal): %s", exc)

    # 2. Cache miss — query Postgres
    result = await db.execute(
        select(models.ChatSession)
        .where(models.ChatSession.user_id == current_user.id)
        .order_by(models.ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()

    # 3. Populate cache (60-second TTL)
    try:
        payload = json.dumps(
            [schemas.ChatSessionResponse.model_validate(s).model_dump(mode="json")
             for s in sessions]
        )
        await _get_redis().setex(cache_key, 60, payload)
    except Exception as exc:
        logger.warning("Redis write failed (non-fatal): %s", exc)

    return sessions


@router.get(
    "/sessions/{session_id}",
    response_model=List[schemas.ChatMessageResponse],
)
async def get_session_messages(
    session_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return every message in a session (oldest first)."""
    await _own_session(session_id, current_user, db)  # Auth check

    result = await db.execute(
        select(models.ChatMessage)
        .where(models.ChatMessage.session_id == session_id)
        .order_by(models.ChatMessage.created_at)
    )
    return result.scalars().all()


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a session and all its messages, then invalidate the cache."""
    session = await _own_session(session_id, current_user, db)
    await db.delete(session)
    await db.commit()

    try:
        await _get_redis().delete(_sessions_cache_key(current_user.id))
    except Exception as exc:
        logger.warning("Redis cache invalidation failed (non-fatal): %s", exc)


@router.post(
    "/sessions/{session_id}/message",
    response_model=schemas.SendMessageResponse,
)
async def send_message(
    session_id: int,
    body: schemas.SendMessageRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Full-response (non-streaming) chat endpoint.
    Saves both the user message and the complete AI reply before returning.
    """
    session = await _own_session(session_id, current_user, db)

    # 1. Auto-title from first message
    if session.title == "New Chat":
        session.title = body.content[:60].strip()
        db.add(session)

    # 2. Persist user message
    user_msg = models.ChatMessage(
        session_id=session_id, role="user", content=body.content
    )
    db.add(user_msg)
    await db.flush()  # Get user_msg.id without a full commit

    # 3. Load last 10 turns for context window
    hist_result = await db.execute(
        select(models.ChatMessage)
        .where(models.ChatMessage.session_id == session_id)
        .order_by(models.ChatMessage.created_at)
    )
    history_rows = hist_result.scalars().all()
    history_dicts = [{"role": m.role, "content": m.content} for m in history_rows[-10:]]

    # 4. Target user's docs (cross-user sharing support)
    target_user_id = body.target_user_id or current_user.id

    # 5. Stream → collect full response (non-streaming endpoint)
    ai_text  = ""
    sources  = []
    async for token in async_query_rag_with_history(
        query_text=body.content,
        history=history_dicts,
        user_id=target_user_id,
    ):
        if token.startswith("\n\n[SOURCES]"):
            sources = json.loads(token.replace("\n\n[SOURCES]", ""))
        else:
            ai_text += token

    # 6. Persist AI reply
    ai_msg = models.ChatMessage(
        session_id=session_id, role="assistant", content=ai_text
    )
    db.add(ai_msg)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(ai_msg)

    logger.info(
        "Session %d: user=%d query=%r → %d source(s)",
        session_id, current_user.id, body.content[:40], len(sources),
    )
    return schemas.SendMessageResponse(
        message=schemas.ChatMessageResponse.model_validate(user_msg),
        ai_message=schemas.ChatMessageResponse.model_validate(ai_msg),
        sources=sources,
    )


# ── SSE Streaming Endpoint (TTFT < 200ms) ─────────────────────────────────────

@router.post("/sessions/{session_id}/stream")
async def stream_message(
    session_id: int,
    body: schemas.SendMessageRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SSE streaming chat endpoint.

    Returns tokens the exact millisecond they arrive from Gemini.
    Frontend connects with `EventSource` or `fetch` + `ReadableStream`.

    SSE protocol:
      data: <token>\\n\\n        — for each text token
      data: [DONE]\\n\\n          — signals end of stream
      data: [SOURCES]<json>\\n\\n  — citation list (sent before DONE)
    """
    session = await _own_session(session_id, current_user, db)

    # Auto-title
    if session.title == "New Chat":
        session.title = body.content[:60].strip()
        db.add(session)
        await db.flush()

    # Persist user message immediately so it appears in the UI right away
    user_msg = models.ChatMessage(
        session_id=session_id, role="user", content=body.content
    )
    db.add(user_msg)
    await db.flush()

    # Load history
    hist_result = await db.execute(
        select(models.ChatMessage)
        .where(models.ChatMessage.session_id == session_id)
        .order_by(models.ChatMessage.created_at)
    )
    history_rows  = hist_result.scalars().all()
    history_dicts = [{"role": m.role, "content": m.content} for m in history_rows[-10:]]
    target_user_id = body.target_user_id or current_user.id

    async def _event_generator() -> AsyncGenerator[str, None]:
        full_text = ""
        try:
            async for token in async_query_rag_with_history(
                query_text=body.content,
                history=history_dicts,
                user_id=target_user_id,
            ):
                if token.startswith("\n\n[SOURCES]"):
                    sources_json = token.replace("\n\n[SOURCES]", "")
                    yield f"data: [SOURCES]{sources_json}\n\n"
                else:
                    full_text += token
                    # Escape newlines in SSE data field
                    safe_token = token.replace("\n", "\\n")
                    yield f"data: {safe_token}\n\n"

            # Persist the complete AI reply in the background
            ai_msg = models.ChatMessage(
                session_id=session_id, role="assistant", content=full_text
            )
            db.add(ai_msg)
            await db.commit()
            await db.refresh(user_msg)

        except Exception as exc:
            logger.exception("Error during SSE stream for session %d: %s", session_id, exc)
            yield f"data: [ERROR]{str(exc)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering for SSE
        },
    )
