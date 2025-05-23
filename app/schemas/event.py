# app/schemas/event.py

import uuid
from datetime import datetime
from typing import List, Optional

from dateutil.rrule import rrulestr
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError


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

    @field_validator("recurrence_pattern")
    def validate_recurrence_pattern(cls, v):
        if v is not None:
            try:
                rrulestr(v)
            except Exception:
                raise PydanticCustomError(
                    "invalid_rrule", "recurrence_pattern must be a valid RRULE string"
                )
        return v

    @model_validator(mode="after")
    def check_times(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise PydanticCustomError(
                "invalid_time_order", "end_time must be after start_time"
            )
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

    @field_validator("recurrence_pattern")
    def validate_recurrence_pattern(cls, v):
        if v is not None:
            try:
                rrulestr(v)
            except Exception:
                raise PydanticCustomError(
                    "invalid_rrule", "recurrence_pattern must be a valid RRULE string"
                )
        return v


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
