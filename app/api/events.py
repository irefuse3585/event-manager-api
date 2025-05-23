# app/api/events.py

import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.event import (
    BatchCreateEventsRequest,
    EventCreate,
    EventRead,
    EventUpdate,
)
from app.schemas.permission import PermissionCreate, PermissionRead
from app.services.event_service import (
    create_event,
    create_events_batch,
    delete_event,
    get_event,
    grant_event_permissions,
    list_events,
    update_event,
)
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/events", tags=["events"])
logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Create a new event. The authenticated user becomes the OWNER.
    """
    event = await create_event(db, current_user.id, data.dict())
    event_read = EventRead.from_orm(event)
    return event_read


@router.post(
    "/batch", response_model=List[EventRead], status_code=status.HTTP_201_CREATED
)
async def create_events_batch_endpoint(
    data: BatchCreateEventsRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Batch create multiple events for the authenticated user.
    Rolls back all if at least one event fails.
    """
    events_data = [event.dict() for event in data.events]
    created_events = await create_events_batch(db, current_user.id, events_data)
    return [EventRead.from_orm(event) for event in created_events]


@router.post(
    "/{event_id}/share",
    response_model=List[PermissionRead],
    status_code=status.HTTP_201_CREATED,
)
async def share_event(
    event_id: uuid.UUID,
    items: List[PermissionCreate],
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Share an event with other users (grant permissions).
    Only OWNER may call.
    """
    data = [item.dict() for item in items]
    perms = await grant_event_permissions(db, current_user.id, event_id, data)
    return [PermissionRead.from_orm(p) for p in perms]


@router.get("", response_model=List[EventRead])
async def list_all(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    List events accessible to the authenticated user. Pagination supported.
    """
    events = await list_events(db, current_user.id, skip, limit)
    logger.info(
        "Listed events for user=%s count=%d", current_user.username, len(events)
    )
    return [EventRead.from_orm(event) for event in events]


@router.get("/{event_id}", response_model=EventRead)
async def get_one(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get a specific event by ID if the user has access.
    """
    event = await get_event(db, current_user.id, event_id)
    logger.info("Event read: id=%s by user=%s", event.id, current_user.username)
    return EventRead.from_orm(event)


@router.put("/{event_id}", response_model=EventRead)
async def update_one(
    event_id: uuid.UUID,
    data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Update an event (only OWNER or EDITOR).
    """
    event = await update_event(
        db, current_user.id, event_id, data.dict(exclude_unset=True)
    )
    return EventRead.from_orm(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_one(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Delete an event (only OWNER).
    """
    await delete_event(db, current_user.id, event_id)
