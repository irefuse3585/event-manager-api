# app/schemas/event.py

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class EventBase(BaseModel):
    title: str = Field(..., max_length=100, examples=["Team meeting"])
    description: Optional[str] = Field(None, examples=["Weekly sync-up"])
    start_time: datetime = Field(..., examples=["2024-05-23T14:00:00Z"])
    end_time: datetime = Field(..., examples=["2024-05-23T15:00:00Z"])
    location: Optional[str] = Field(None, examples=["Zoom"])
    is_recurring: bool = Field(False, description="Is the event recurring?")
    recurrence_pattern: Optional[str] = Field(
        None, max_length=100, examples=["RRULE:FREQ=WEEKLY;BYDAY=MO"]
    )

    @model_validator(mode="after")
    def check_times(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class EventCreate(EventBase):
    pass


class BatchCreateEventsRequest(BaseModel):
    events: List[EventCreate]


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    is_recurring: Optional[bool] = None
    recurrence_pattern: Optional[str] = Field(None, max_length=100)


class PermissionRead(BaseModel):
    user_id: uuid.UUID = Field(..., description="User with access")
    role: str = Field(..., examples=["OWNER", "EDITOR", "VIEWER"])

    class Config:
        from_attributes = True


class EventRead(EventBase):
    id: uuid.UUID = Field(..., description="Event unique identifier")
    owner_id: uuid.UUID = Field(..., description="Owner of event")
    permissions: Optional[List[PermissionRead]] = None

    class Config:
        from_attributes = True
