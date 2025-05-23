# app/models/history.py

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class History(Base):
    """
    ORM model for storing event version snapshots with attribution.

    Each record stores a snapshot of an Event's data at a given version,
    who made the change, and when.
    """

    __tablename__ = "histories"

    # Unique UUID primary key for the history entry
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign key to the original event
    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event = relationship("Event", back_populates="histories")

    # Sequential version number per event (starting at 1)
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # JSONB snapshot storing full event data as dict
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Timestamp when this version was created
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # User who made the change, can be NULL if user deleted
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_by_user = relationship("User", back_populates="histories")
