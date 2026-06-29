"""
app/api/v1/ws.py

WebSocket endpoint for real-time push notifications.

Auth: JWT passed as ?token=<jwt> query param (browsers can't set Authorization
      headers on WebSocket connections). Token is validated before accept().

Pattern:
  Two concurrent asyncio tasks run for each connected client:
    1. forward_messages — subscribes to Redis pub/sub channel for this user,
       pushes every arriving message to the WebSocket.
    2. watch_disconnect — reads incoming frames to detect client-side close.

  asyncio.wait(FIRST_COMPLETED) means whichever task ends first (client
  disconnects OR Redis fails) tears down the other and cleans up — no zombies.

Redis channel format:  "doc:ready:{user_id}"
Message payload:
  {"type": "document.ready", "document_id": 5, "filename": "notes.pdf", "status": "completed"}
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt

from app.config import settings
from app.infrastructure.redis_client import get_redis

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(..., description="Access JWT — required because browsers cannot set auth headers on WebSocket"),
):
    # ── 1. Auth before accept ─────────────────────────────────────────────────
    # Reject invalid tokens without ever opening the connection.
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("user_id")
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    logger.info("WebSocket opened for user_id=%d", user_id)

    # ── 2. Subscribe to this user's Redis pub/sub channel ────────────────────
    # pubsub() pulls a dedicated connection from the pool — the shared
    # get_redis() client remains usable for cache / rate-limit operations.
    pubsub = get_redis().pubsub()
    channel = f"doc:ready:{user_id}"
    await pubsub.subscribe(channel)

    # ── 3. Run two concurrent tasks ───────────────────────────────────────────

    async def forward_messages() -> None:
        """Listen on Redis, push each message to the browser."""
        async for message in pubsub.listen():
            if message["type"] == "message":
                # decode_responses=True → data is already a str
                await websocket.send_text(message["data"])

    async def watch_disconnect() -> None:
        """Consume incoming frames; raises WebSocketDisconnect on client close."""
        try:
            while True:
                await websocket.receive_bytes()
        except WebSocketDisconnect:
            pass

    forward_task = asyncio.create_task(forward_messages())
    disconnect_task = asyncio.create_task(watch_disconnect())

    try:
        # Block until either task finishes (client disconnects or Redis errors)
        await asyncio.wait(
            {forward_task, disconnect_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        forward_task.cancel()
        disconnect_task.cancel()
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        logger.info("WebSocket closed for user_id=%d", user_id)
