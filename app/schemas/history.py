# app/schemas/history.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class HistoryRead(BaseModel):
    """
    Response model for a single history version of an event.
    """

    id: UUID = Field(..., description="Unique ID of the history record")
    event_id: UUID = Field(..., description="ID of the event")
    version: int = Field(..., description="Sequential version number of the event")
    data: dict = Field(..., description="Snapshot of the event data at this version")
    timestamp: datetime = Field(..., description="When this version was created")
    changed_by: Optional[UUID] = Field(
        None, description="User ID who made the change (may be null)"
    )

    class Config:
        orm_mode = True
