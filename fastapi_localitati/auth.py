"""
Authentication and JWT token management for FastAPI application.

This module defines login, token generation, and verification logic.
It uses JWT (JSON Web Tokens) for secure stateless authentication.

Compatible with Pydantic v2 and async SQLAlchemy.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from . import models, schemas
from .database import async_session_maker
from .settings import get_settings

settings = get_settings()

# OAuth2 scheme (used by FastAPI to extract the Bearer token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Router
router = APIRouter(tags=["Auth"])


# ============================================================
# 🧠 HELPER FUNCTIONS
# ============================================================


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify user password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plain password."""
    return pwd_context.hash(password)


async def get_user_by_username(
    db: AsyncSession, username: str
) -> Optional[models.User]:
    """Retrieve user from DB by username."""
    result = await db.execute(
        select(models.User).filter(models.User.username == username)
    )
    return result.scalars().first()


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> Optional[models.User]:
    """Authenticate user credentials."""
    user = await get_user_by_username(db, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def _utc_timestamp(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a short-lived access token with explicit type claim."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {
        **data,
        "type": "access",
        "iat": _utc_timestamp(now),
        "nbf": _utc_timestamp(now),
        "exp": _utc_timestamp(expire),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a long-lived refresh token with explicit type claim."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        **data,
        "type": "refresh",
        "iat": _utc_timestamp(now),
        "nbf": _utc_timestamp(now),
        "exp": _utc_timestamp(expire),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def verify_access_token(token: str = Depends(oauth2_scheme)) -> dict:
    """Verify JWT access token and return decoded payload. Reject refresh tokens."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalid sau expirat",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "access":
            raise credentials_exception
        username: str | None = payload.get("sub")
        if not username:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception


# -------------------- DATABASE SESSION --------------------
async def get_db():
    """Dependency to provide Async DB session."""
    async with async_session_maker() as session:
        yield session


# -------------------- CURRENT USER DEPENDENCY --------------------
async def get_current_user(
    payload: dict = Depends(verify_access_token),
    db: AsyncSession = Depends(get_db),
) -> models.User:
    username = payload.get("sub")
    result = await db.execute(
        select(models.User).where(models.User.username == username)
    )
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilizator inactiv sau inexistent",
        )
    return user


# -------------------- VERY BASIC RATE LIMITER --------------------
# Note: This is an in-memory, per-process limiter adequate only for single-instance deployments.
from collections import defaultdict, deque
import time as _time

_rate_buckets: dict[str, deque] = defaultdict(deque)


async def rate_limit(ip: str, limit_per_minute: int) -> None:
    window = 60
    now = _time.time()
    dq = _rate_buckets[ip]
    # Purge old entries
    while dq and now - dq[0] > window:
        dq.popleft()
    if len(dq) >= limit_per_minute:
        raise HTTPException(
            status_code=429, detail="Prea multe cereri, încearcă din nou mai târziu"
        )
    dq.append(now)


from fastapi import Request


async def rate_limiter(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    await rate_limit(client_ip, settings.RATE_LIMIT_PER_MINUTE)


# ============================================================
# 🔑 API ROUTES
# ============================================================


@router.post("/token", response_model=schemas.Token, tags=["Auth"])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return access + refresh tokens."""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        # 401 here to be compatible with OAuth2 password flow in Swagger
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nume utilizator sau parolă incorectă",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    return schemas.Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/token/refresh", response_model=schemas.Token, tags=["Auth"])
async def refresh_access_token(body: schemas.RefreshRequest):
    """Generate new access and refresh tokens using a valid refresh token (rotation)."""
    try:
        payload = jwt.decode(
            body.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=400, detail="Tokenul nu este de tip refresh"
            )
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=400, detail="Refresh token fără sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalid sau expirat")

    new_access_token = create_access_token(data={"sub": username})
    # Rotation: issue a new refresh token every time
    new_refresh_token = create_refresh_token(data={"sub": username})

    return schemas.Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )
