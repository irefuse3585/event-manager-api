from typing import Optional

from pydantic import BaseModel, Field, model_validator


class LoginRequest(BaseModel):
    """
    Request body for login and register endpoints.
    Must include either username or email, plus password.
    """

    username: Optional[str] = Field(
        None, examples=["john_doe"], description="Username for login"
    )
    email: Optional[str] = Field(
        None, examples=["john@example.com"], description="Email for login"
    )
    password: str = Field(
        ..., examples=["StrongPassword123!"], description="User's password"
    )

    @model_validator(mode="before")
    def check_username_or_email(cls, values: dict) -> dict:
        if not values.get("username") and not values.get("email"):
            raise ValueError("Either username or email must be provided")
        return values


class TokenResponse(BaseModel):
    """
    Response model containing both access and refresh tokens.
    """

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Type of token")


class RefreshRequest(BaseModel):
    """
    Request body for refresh and logout endpoints.
    """

    refresh_token: str = Field(..., description="JWT refresh token")
