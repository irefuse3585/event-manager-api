from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_refresh_token
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth_service import (
    authenticate_user,
    create_access_token_for_user,
    create_refresh_token_for_user,
    get_user_by_id,
    is_refresh_token_revoked,
    register_user,
    revoke_refresh_token,
)
from app.utils.exceptions import ConflictError, UnauthorizedError
from app.utils.response import auto_response

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    request: Request,
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Register user and issue both tokens, storing refresh token in httpOnly cookie.
    Returns either JSON or MessagePack response.
    """
    try:
        user = await register_user(db, data)
    except ConflictError as e:
        # Let FastAPI handle ConflictError, it will return 409
        raise e
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
    return auto_response(
        request,
        {"access_token": access, "refresh_token": "stored in httpOnly cookie"},
        status.HTTP_201_CREATED,
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
    Authenticate user and return new tokens.
    Sets refresh token in httpOnly cookie.
    Supports both JSON and MessagePack response formats.
    """
    try:
        user = await authenticate_user(db, data)
    except UnauthorizedError as e:
        raise e
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
    return auto_response(
        request, {"access_token": access, "refresh_token": "stored in httpOnly cookie"}
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_REFRESH)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    """
    Rotate tokens:
    - Extract refresh token from cookie
    - Validate and revoke old token
    - Issue new tokens and set new cookie
    Returns either JSON or MessagePack depending on Accept header.
    """
    token = request.cookies.get("refresh_token")
    if not token:
        raise UnauthorizedError("Refresh token missing")
    if await is_refresh_token_revoked(token):
        raise UnauthorizedError("Refresh token revoked")

    try:
        payload: dict[str, Any] = decode_refresh_token(token)
        user_id = payload.get("sub")
        if not isinstance(user_id, str):
            raise UnauthorizedError("Invalid token payload")
    except Exception:
        raise UnauthorizedError("Invalid refresh token")

    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
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
    return auto_response(
        request,
        {"access_token": new_access, "refresh_token": "stored in httpOnly cookie"},
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request):
    """
    Revoke provided refresh token from cookie.
    """
    token = request.cookies.get("refresh_token")
    if token:
        await revoke_refresh_token(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
