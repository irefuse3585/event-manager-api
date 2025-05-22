# app/core/secutity.py

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing context (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """
    Hash plaintext password using bcrypt.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify plaintext password against stored bcrypt hash.
    """
    return pwd_context.verify(plain_password, hashed_password)


def _now() -> datetime:
    return datetime.utcnow()


def create_access_token(
    subject: str, role: str, expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token with security best practices.
    Payload includes:
    - sub: subject (user ID)
    - role: user's role
    - iat: issued-at timestamp
    - exp: expiration timestamp
    - iss: issuer
    - aud: audience
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    now = _now()
    payload: Dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + expires_delta,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    return jwt.encode(
        payload,
        settings.ACCESS_TOKEN_SECRET,
        algorithm=settings.ACCESS_TOKEN_ALGORITHM,
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token, verifying audience and issuer.
    """
    try:
        return jwt.decode(
            token,
            settings.ACCESS_TOKEN_SECRET,
            algorithms=[settings.ACCESS_TOKEN_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
    except JWTError as e:
        raise ValueError("Invalid access token") from e


def create_refresh_token(
    subject: str, expires_delta: Optional[timedelta] = None
) -> Tuple[str, str]:
    """
    Create a JWT refresh token with a unique jti, issuer, and audience.
    Returns tuple (token, jti).
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    now = _now()
    jti = str(uuid.uuid4())
    payload: Dict[str, Any] = {
        "sub": subject,
        "jti": jti,
        "iat": now,
        "exp": now + expires_delta,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    token = jwt.encode(
        payload,
        settings.REFRESH_TOKEN_SECRET,
        algorithm=settings.REFRESH_TOKEN_ALGORITHM,
    )
    return token, jti


def decode_refresh_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT refresh token, verifying audience and issuer.
    """
    try:
        return jwt.decode(
            token,
            settings.REFRESH_TOKEN_SECRET,
            algorithms=[settings.REFRESH_TOKEN_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
    except JWTError as e:
        raise ValueError("Invalid refresh token") from e
