"""
app/services/audit_service.py

Write-only service for the append-only audit log.
This module only exposes one function: log(). There is intentionally no
read, update, or delete function — the log is immutable by design.

Usage (in a FastAPI route handler):
    background_tasks.add_task(
        audit_service.log,
        user_id=current_user.id,
        action="document.upload",
        resource_id=doc.id,
        metadata={"filename": file.filename, "size_bytes": len(content)},
        ip_address=request.client.host if request.client else None,
    )

The background task runs after the response is sent to the client, so a
slow or failing audit write never affects the user's perceived latency.
Failures are logged as errors but never propagated.
"""

import logging

from app.database import AsyncSessionLocal
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


# ── Action constants ──────────────────────────────────────────────────────────
# Use these instead of bare strings so typos are caught at import time.

class Action:
    AUTH_LOGIN           = "auth.login"
    AUTH_LOGOUT          = "auth.logout"
    DOCUMENT_UPLOAD      = "document.upload"
    DOCUMENT_DELETE      = "document.delete"
    CHAT_QUERY           = "chat.query"
    CHAT_SESSION_CREATE  = "chat.session.create"
    CHAT_SESSION_DELETE  = "chat.session.delete"


async def log(
    user_id: int | None,
    action: str,
    resource_id: int | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Write one audit log entry. Opens and closes its own DB session so it
    can safely be used as a FastAPI BackgroundTask (the request session is
    already closed by the time background tasks run).
    """
    try:
        async with AsyncSessionLocal() as db:
            entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_id=resource_id,
                metadata_=metadata,
                ip_address=ip_address,
            )
            db.add(entry)
            await db.commit()
    except Exception as exc:
        # Audit failure must NEVER surface to the user — log it and move on.
        logger.error("Audit log write failed [action=%s user=%s]: %s", action, user_id, exc)
