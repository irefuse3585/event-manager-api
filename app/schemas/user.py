# app/schemas/user.py

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class UserRead(BaseModel):
    """
    Read-only user schema for API responses.
    """

    id: UUID = Field(..., description="User unique identifier")
    username: str = Field(..., description="Unique username")
    email: EmailStr = Field(..., description="User's email address")
    is_active: bool = Field(..., description="Is the user active")
    role: UserRole = Field(..., description="User role")

    class Config:
        from_attributes = True  # Allows Pydantic to work with SQLAlchemy models
