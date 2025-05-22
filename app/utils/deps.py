# app/utils/deps.py

import logging
from typing import Any, Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.redis import redis_client
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.auth_service import get_user_by_id
from app.utils.exceptions import ForbiddenError, UnauthorizedError

# Initialize logger for this module
logger = logging.getLogger(__name__)

# OAuth2 scheme will look for “Authorization: Bearer <token>”
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode JWT, check revocation in Redis, fetch user from DB.
    Logs warnings on invalid token usage or inactive user.
    """
    try:
        payload: dict[str, Any] = decode_access_token(token)
    except ValueError:
        logger.warning("Invalid JWT token provided.")
        raise UnauthorizedError("Invalid token")

    # Check if the token has been revoked in Redis
    if await redis_client.get(f"revoked_token:{token}"):
        logger.warning("Attempted use of revoked JWT token.")
        raise UnauthorizedError("Token has been revoked")

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        logger.warning("JWT token missing or has invalid 'sub' claim.")
        raise UnauthorizedError("Invalid token payload")

    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
        logger.warning(
            "Attempted authentication with inactive or non-existent user (user_id=%s)",
            user_id,
        )
        raise UnauthorizedError("Inactive or non-existent user")

    return user


def require_role(required_role: UserRole) -> Callable:
    """
    Dependency factory to check if current user has the required role.
    Logs warning on forbidden access attempt.
    """

    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role != required_role:
            logger.warning(
                "Access denied for user '%s': required role '%s', actual role '%s'",
                user.username,
                required_role,
                user.role,
            )
            raise ForbiddenError(
                f"User does not have the required role: {required_role}"
            )
        return user

    return role_checker
