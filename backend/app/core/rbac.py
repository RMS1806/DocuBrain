"""
app/core/rbac.py

Role-Based Access Control (RBAC) policy layer.

All role → permission mappings live here. No other file should hard-code a role
string check. To add a new role: add one entry to ROLE_PERMISSIONS. Every
enforcement point (require_permission, has_permission) updates automatically.

Permission naming convention: "<resource>:<action>"
  documents:read_own      — read your own documents
  documents:read_client   — read a linked client's documents (professional only)
  documents:upload        — upload a new document
  documents:delete_own    — delete your own document
  chat:read               — list/read chat sessions and messages
  chat:write              — send a message (triggers RAG + LLM)
  network:link_professional — send a link invite to a professional
  network:view_clients    — list your linked clients (professional only)
"""

from fastapi import Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.models import User

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "client": {
        "documents:read_own",
        "documents:upload",
        "documents:delete_own",
        "chat:read",
        "chat:write",
        "network:link_professional",
    },
    "professional": {
        "documents:read_own",
        "documents:read_client",
        "documents:upload",
        "documents:delete_own",
        "chat:read",
        "chat:write",
        "network:view_clients",
    },
}


def has_permission(role: str, permission: str) -> bool:
    """
    Sync helper for service-layer conditional checks.
    Use require_permission() for FastAPI route/dependency enforcement.
    """
    return permission in ROLE_PERMISSIONS.get(role, set())


def require_permission(permission: str):
    """
    FastAPI dependency factory. Raises HTTP 403 if the authenticated user's
    role does not carry the requested permission.

    Usage:
        @router.get("/professional/clients")
        async def get_clients(
            _: None = Depends(require_permission("network:view_clients")),
            current_user: User = Depends(get_current_user),
        ):
    """

    async def _enforce(current_user: User = Depends(get_current_user)) -> None:
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your role ('{current_user.role}') does not have '{permission}' permission.",
            )

    return _enforce
