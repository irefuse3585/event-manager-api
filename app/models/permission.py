# app/models/permission.py

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PermissionRole


class Permission(Base):
    """
    ORM model for event sharing permissions.
    """

    __tablename__ = "permissions"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign keys to event and user
    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Role: Owner, Editor or Viewer
    role: Mapped[PermissionRole] = mapped_column(
        SAEnum(
            PermissionRole,
            name="permission_role",
            native_enum=False,
        ),
        nullable=False,
        default=PermissionRole.VIEWER,
    )

    # Relations
    event = relationship("Event", back_populates="permissions")
    user = relationship("User", back_populates="permissions")
