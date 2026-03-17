"""
backend/app/auth.py

Async-first authentication: register, login, and the get_current_user guard.
All DB operations use SQLAlchemy AsyncSession so auth never blocks the event loop.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas, utils
from app.database import get_db

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


@router.post("/register", response_model=schemas.Token)
async def register(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    # 1. Check if email is already taken
    result = await db.execute(
        select(models.User).where(models.User.email == user.email)
    )
    db_user = result.scalars().first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2. Hash password & create user
    hashed_password = utils.hash_password(user.password)
    new_user = models.User(
        email=user.email, password=hashed_password, role=user.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # 3. Issue JWT
    access_token = utils.create_access_token(
        data={"sub": new_user.email, "user_id": new_user.id, "role": new_user.role}
    )
    return {"access_token": access_token, "token_type": "bearer", "role": new_user.role}


@router.post("/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # 1. Find user by email
    result = await db.execute(
        select(models.User).where(models.User.email == form_data.username)
    )
    user = result.scalars().first()
    if not user or not utils.verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Issue JWT
    access_token = utils.create_access_token(
        data={"sub": user.email, "user_id": user.id, "role": user.role}
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}


# ── Auth Guard Dependency ──────────────────────────────────────────────────────
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> models.User:
    """
    Decodes the Bearer JWT and fetches the matching User row.
    Fully async — safe to use in any async FastAPI route.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, utils.SECRET_KEY, algorithms=[utils.ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user