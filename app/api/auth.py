# app/api/auth.py

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_refresh_token
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.auth_service import (
    authenticate_user,
    create_access_token_for_user,
    create_refresh_token_for_user,
    get_user_by_id,
    is_refresh_token_revoked,
    register_user,
    revoke_refresh_token,
)
from app.utils.exceptions import UnauthorizedError

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")
security_logger = logging.getLogger("app.security")


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    data: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user and issue both tokens, setting refresh in httpOnly cookie.
    """
    user = await register_user(db, data)
    access = await create_access_token_for_user(user)
    refresh = await create_refresh_token_for_user(user)
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    return TokenResponse(
        access_token=access,
        refresh_token="stored in httpOnly cookie",
        token_type="bearer",
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user and return new tokens, setting refresh in httpOnly cookie.
    """
    user = await authenticate_user(db, data)
    access = await create_access_token_for_user(user)
    refresh = await create_refresh_token_for_user(user)
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    return TokenResponse(
        access_token=access,
        refresh_token="stored in httpOnly cookie",
        token_type="bearer",
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_REFRESH)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Rotate tokens: extract, validate, revoke old refresh, issue new pair.
    """
    token = request.cookies.get("refresh_token")
    if not token:
        security_logger.warning("Refresh token missing in request cookies")
        raise UnauthorizedError("Refresh token missing")
    if await is_refresh_token_revoked(token):
        security_logger.warning("Refresh token revoked or reused")
        raise UnauthorizedError("Refresh token revoked")

    try:
        payload: dict[str, Any] = decode_refresh_token(token)
        user_id = payload.get("sub")
        if not isinstance(user_id, str):
            security_logger.warning("Invalid refresh token payload")
            raise UnauthorizedError("Invalid token payload")
    except Exception:
        security_logger.warning("Invalid refresh token (decode error)")
        raise UnauthorizedError("Invalid refresh token")

    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
        security_logger.warning("Refresh token: invalid user id=%s", user_id)
        raise UnauthorizedError("Invalid user")

    await revoke_refresh_token(token)
    new_access = await create_access_token_for_user(user)
    new_refresh = await create_refresh_token_for_user(user)
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    logger.info("Token refreshed for user: id=%s username=%s", user.id, user.username)
    audit_logger.info(
        "Token refresh: id=%s username=%s email=%s", user.id, user.username, user.email
    )
    return TokenResponse(
        access_token=new_access,
        refresh_token="stored in httpOnly cookie",
        token_type="bearer",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
):
    """
    Revoke provided refresh token from cookie and clear cookie.
    """
    token = request.cookies.get("refresh_token")
    if token:
        await revoke_refresh_token(token)
        logger.info("User logged out: refresh token revoked")
        audit_logger.info("User logout (refresh token revoked)")
    else:
        security_logger.warning("Logout called with no refresh token present")
    # Clear the cookie
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    # 204 responses should have no body (just status)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
