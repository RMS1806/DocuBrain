from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.auth import Token, UserCreate
from app.services import audit_service, auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"
_REFRESH_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def _set_refresh_cookie(response: Response, token: str) -> None:
    """
    Attach the refresh token as an httpOnly cookie.
    - httponly=True  : JS cannot read it (XSS protection)
    - secure=True    : only sent over HTTPS (False in dev so localhost works)
    - samesite       : "none" for cross-origin prod; "lax" for same-origin dev
    - path="/auth"   : browser only sends this cookie to /auth/* routes
    """
    is_prod = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=is_prod,
        samesite="none" if is_prod else "lax",
        max_age=_REFRESH_MAX_AGE,
        path="/auth",
    )


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/register", response_model=Token)
async def register(
    request: Request,
    user: UserCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    access_token, refresh_token, user_id = await auth_service.register_user(
        db, user.email, user.password
    )
    _set_refresh_cookie(response, refresh_token)
    background_tasks.add_task(
        audit_service.log,
        user_id=user_id,
        action=audit_service.Action.AUTH_LOGIN,
        metadata={"event": "register"},
        ip_address=_client_ip(request),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    access_token, refresh_token, user_id = await auth_service.login_user(
        db, form_data.username, form_data.password
    )
    _set_refresh_cookie(response, refresh_token)
    background_tasks.add_task(
        audit_service.log,
        user_id=user_id,
        action=audit_service.Action.AUTH_LOGIN,
        ip_address=_client_ip(request),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Silently exchange an expiring access token for a fresh one.
    The browser sends the httpOnly cookie automatically — no JS involvement.
    """
    old_token = request.cookies.get(_REFRESH_COOKIE)
    if not old_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token present",
        )

    access_token, new_refresh_token = await auth_service.refresh_tokens(
        db, old_token
    )
    _set_refresh_cookie(response, new_refresh_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response):
    """
    Revoke the refresh token immediately (deletes from Redis) and clear the cookie.
    The access token remains valid until its 15-min expiry — acceptable trade-off.
    """
    token = request.cookies.get(_REFRESH_COOKIE)
    if token:
        await auth_service.logout(token)
    response.delete_cookie(_REFRESH_COOKIE, path="/auth")
