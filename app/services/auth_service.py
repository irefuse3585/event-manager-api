# app/services/auth_service.py

from datetime import timedelta

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.utils.exceptions import ConflictError, UnauthorizedError


async def register_user(db: AsyncSession, data: LoginRequest) -> User:
    """
    Register a new user:
    - ensure username or email is unique
    - hash the password
    - insert into DB
    """
    stmt = select(User).where(
        (User.username == data.username) | (User.email == data.email)
    )
    exists = (await db.execute(stmt)).scalars().first()
    if exists:
        raise ConflictError("Username or email already registered")

    hashed = get_password_hash(data.password)
    user = User(username=data.username, email=data.email, hashed_password=hashed)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, data: LoginRequest) -> User:
    """
    Authenticate credentials:
    - lookup by username or email
    - verify password match
    """
    stmt = select(User).where(
        (User.username == data.username) | (User.email == data.email)
    )
    user = (await db.execute(stmt)).scalars().first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise UnauthorizedError("Invalid username/email or password")
    return user


def create_access_token_for_user(user: User) -> str:
    """
    Generate a JWT access token for the given user.
    """
    expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_access_token(subject=str(user.id), expires_delta=expire)


def refresh_access_token(token: str) -> str:
    """
    Decode an existing token and issue a new one with reset expiry.
    """
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedError("Token payload missing subject")
    except (JWTError, ValueError):
        # catch both JWT-specific errors and malformed-token ValueError
        raise UnauthorizedError("Invalid token")

    expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_access_token(subject=user_id, expires_delta=expire)
