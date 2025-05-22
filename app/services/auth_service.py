# app/services/auth_service.py

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_password_hash,
    verify_password,
)
from app.db.redis import redis_client
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
    existing_user = (await db.execute(stmt)).scalars().first()
    if existing_user:
        raise ConflictError("Username or email already registered")

    hashed_password = get_password_hash(data.password)
    new_user = User(
        username=data.username, email=data.email, hashed_password=hashed_password
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


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


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """
    Fetch user by UUID (string).
    """
    stmt = select(User).where(User.id == user_id)
    return (await db.execute(stmt)).scalars().first()


async def create_access_token_for_user(user: User) -> str:
    """
    Issue access token embedding user's role.
    """
    return create_access_token(subject=str(user.id), role=user.role.value)


async def create_refresh_token_for_user(user: User) -> str:
    """
    Issue refresh token and store its jti in Redis.
    """
    token, jti = create_refresh_token(subject=str(user.id))
    payload = decode_refresh_token(token)
    ttl = payload["exp"] - int(datetime.utcnow().timestamp())
    await redis_client.set(f"refresh:jti:{jti}", str(user.id), ex=ttl)
    return token


async def revoke_refresh_token(token: str) -> None:
    """
    Revoke a refresh token by deleting its jti from Redis.
    """
    try:
        payload = decode_refresh_token(token)
        jti = payload.get("jti")
    except ValueError:
        return
    if jti:
        await redis_client.delete(f"refresh:jti:{jti}")


async def is_refresh_token_revoked(token: str) -> bool:
    """
    Check revocation status: if jti missing in Redis, token is revoked.
    """
    try:
        payload = decode_refresh_token(token)
        jti = payload.get("jti")
    except ValueError:
        return True
    if not jti:
        return True
    return not bool(await redis_client.exists(f"refresh:jti:{jti}"))
