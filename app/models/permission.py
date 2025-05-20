import uuid

from sqlalchemy import Column, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.enums import PermissionRole  # Enum для ролей доступа


class Permission(Base):
    """
    ORM model for event sharing permissions.
    """

    __tablename__ = "permissions"

    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys to event and user
    event_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Role: Owner, Editor or Viewer
    role = Column(Enum(PermissionRole), nullable=False)

    # Relations
    event = relationship("Event", back_populates="permissions")
    user = relationship("User", back_populates="permissions")
