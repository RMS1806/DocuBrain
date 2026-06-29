from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.chat import ChatMessageResponse, ChatSessionResponse, SendMessageRequest
from app.services import audit_service, chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
async def create_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await chat_service.create_session(db, current_user)


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await chat_service.list_sessions(db, current_user)


@router.get("/sessions/{session_id}", response_model=List[ChatMessageResponse])
async def get_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await chat_service.get_messages(db, session_id, current_user)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await chat_service.delete_session(db, session_id, current_user)


@router.post("/sessions/{session_id}/stream")
async def stream_message(
    session_id: int,
    body: SendMessageRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    generator = await chat_service.stream_response(
        db, session_id, body.content, current_user
    )
    background_tasks.add_task(
        audit_service.log,
        user_id=current_user.id,
        action=audit_service.Action.CHAT_QUERY,
        resource_id=session_id,
        metadata={"query_length": len(body.content)},
        ip_address=request.client.host if request.client else None,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
