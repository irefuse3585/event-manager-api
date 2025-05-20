import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class History(Base):
    """
    ORM model for storing event version snapshots.
    """

    __tablename__ = "histories"

    # Primary key
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to the event
    event_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    event = relationship("Event", back_populates="histories")

    # Incremental version number
    version = Column(Integer, nullable=False)

    # JSONB snapshot of all event fields
    data = Column(JSONB, nullable=False)

    # Timestamp of change
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Who made the change
    changed_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_by_user = relationship("User", back_populates="histories")
