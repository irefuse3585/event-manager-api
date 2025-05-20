# app/schemas/auth.py

from typing import Optional

from pydantic import BaseModel, ValidationError, model_validator


class LoginRequest(BaseModel):
    """
    Request body for login and register endpoints.
    User must provide either username or email, and a password.
    """

    username: Optional[str]
    email: Optional[str]
    password: str

    @model_validator(mode="before")
    def check_username_or_email(cls, values: dict) -> dict:
        """
        Ensure that at least one of username or email is provided.
        This runs before field validation.
        """
        if not (values.get("username") or values.get("email")):
            raise ValidationError("Either username or email must be provided")
        return values


class TokenResponse(BaseModel):
    """
    Response model containing the access token and its type.
    """

    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """
    Request body for token refresh endpoint.
    """

    refresh_token: str
