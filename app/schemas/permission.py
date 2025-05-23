import uuid

from pydantic import BaseModel, Field

from app.models.enums import PermissionRole


class PermissionCreate(BaseModel):
    user_id: uuid.UUID = Field(..., description="User to grant access to")
    role: PermissionRole = Field(
        ..., description="Role to assign: OWNER, EDITOR, or VIEWER"
    )


class PermissionUpdate(BaseModel):
    role: PermissionRole = Field(..., description="New role: OWNER, EDITOR, or VIEWER")


class PermissionRead(BaseModel):
    user_id: uuid.UUID
    role: PermissionRole

    class Config:
        from_attributes = True
