# app/services/auth_service.py

import logging
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

# Regular logger for internal operations
logger = logging.getLogger(__name__)
# Audit logger for tracking user-related actions
audit_logger = logging.getLogger("audit")
# Security logger for warnings and auth failures (optional)
security_logger = logging.getLogger("app.security")


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
        security_logger.warning(
            "Registration attempt with existing username or email: %s, %s",
            data.username,
            data.email,
        )
        raise ConflictError("Username or email already registered")

    hashed_password = get_password_hash(data.password)
    new_user = User(
        username=data.username, email=data.email, hashed_password=hashed_password
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    logger.info(
        "User registered successfully: id=%s username=%s",
        new_user.id,
        new_user.username,
    )
    audit_logger.info(
        f"User registered: id={new_user.id} username={new_user.username} "
        f"email={new_user.email}"
    )
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
        security_logger.warning(
            "Failed login attempt for username=%s or email=%s",
            data.username,
            data.email,
        )
        raise UnauthorizedError("Invalid username/email or password")
    logger.info("User authenticated: id=%s username=%s", user.id, user.username)
    audit_logger.info(
        f"User login: id={user.id} username={user.username} email={user.email}"
    )
    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """
    Fetch user by UUID (string).
    """
    user = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if user:
        logger.debug("Fetched user by id: %s", user_id)
    else:
        logger.warning("User not found by id: %s", user_id)
    return user


async def create_access_token_for_user(user: User) -> str:
    """
    Issue access token embedding user's role.
    """
    logger.debug("Issuing access token for user_id=%s role=%s", user.id, user.role)
    return create_access_token(subject=str(user.id), role=user.role.value)


async def create_refresh_token_for_user(user: User) -> str:
    """
    Issue refresh token and store its jti in Redis.
    """
    token, jti = create_refresh_token(subject=str(user.id))
    payload = decode_refresh_token(token)
    ttl = payload["exp"] - int(datetime.utcnow().timestamp())
    await redis_client.set(f"refresh:jti:{jti}", str(user.id), ex=ttl)
    logger.debug("Refresh token issued and stored in Redis for user_id=%s", user.id)
    return token


async def revoke_refresh_token(token: str) -> None:
    """
    Revoke a refresh token by deleting its jti from Redis.
    """
    try:
        payload = decode_refresh_token(token)
        jti = payload.get("jti")
    except ValueError:
        logger.warning("Attempted to revoke invalid refresh token")
        return
    if jti:
        await redis_client.delete(f"refresh:jti:{jti}")
        logger.info("Refresh token revoked: jti=%s", jti)
        audit_logger.info(f"Refresh token revoked: jti={jti}")


async def is_refresh_token_revoked(token: str) -> bool:
    """
    Check revocation status: if jti missing in Redis, token is revoked.
    """
    try:
        payload = decode_refresh_token(token)
        jti = payload.get("jti")
    except ValueError:
        logger.warning("Token revoked check failed: invalid token")
        return True
    if not jti:
        logger.warning("Token revoked check: missing jti")
        return True
    exists = await redis_client.exists(f"refresh:jti:{jti}")
    logger.debug("Refresh token jti=%s exists in Redis: %s", jti, bool(exists))
    return not bool(exists)
