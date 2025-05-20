from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing context (bcrypt algorithm)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """
    Generate a hashed password from a plaintext password.

    :param password: Plaintext password
    :return: Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a hashed password.

    :param plain_password: Plaintext password provided by the user
    :param hashed_password: Hashed password stored in the database
    :return: True if passwords match, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token for the given subject (usually user ID).

    :param subject: The identifier of the user (e.g., user ID)
    :param expires_delta: Token expiration duration; uses default if not specified
    :return: JWT token as string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.utcnow() + expires_delta
    payload = {"sub": subject, "exp": expire}
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return token


def decode_access_token(token: str) -> dict:
    """
    Decode a JWT token to retrieve the payload data.

    :param token: JWT token string
    :return: Payload data as a dictionary
    :raises ValueError: if the token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except JWTError as e:
        raise ValueError("Invalid token") from e
