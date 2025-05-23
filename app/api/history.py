import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.event import EventRead
from app.schemas.history import HistoryRead
from app.services.event_service import get_event
from app.services.history_service import (
    get_diff_between_versions,
    get_event_history_versions,
    get_event_version,
    rollback_event_to_version,
)
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/events", tags=["events"])

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")


@router.get("/{event_id}/history", response_model=List[HistoryRead])
async def get_history(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Retrieve all history versions of the event."""
    await get_event(db, current_user.id, event_id)
    versions = await get_event_history_versions(db, event_id)
    logger.info(
        "User %s fetched history list for event %s", current_user.username, event_id
    )
    return versions


@router.get("/{event_id}/history/{version_id}", response_model=HistoryRead)
async def get_version(
    event_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Retrieve a specific history version by ID."""
    await get_event(db, current_user.id, event_id)
    version = await get_event_version(db, version_id)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Version not found"
        )
    logger.info(
        "User %s fetched history version %s for event %s",
        current_user.username,
        version_id,
        event_id,
    )
    return version


@router.post("/{event_id}/rollback/{version_id}", response_model=EventRead)
async def rollback_version(
    event_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Rollback event to a previous version."""
    await get_event(db, current_user.id, event_id)
    event = await rollback_event_to_version(db, event_id, version_id, current_user.id)
    logger.info(
        "User %s rolled back event %s to version %s",
        current_user.username,
        event_id,
        version_id,
    )
    audit_logger.info(
        "Rollback event: user=%s event=%s version=%s",
        current_user.id,
        event_id,
        version_id,
    )
    return EventRead.from_orm(event)


@router.get("/{event_id}/diff/{version_id1}/{version_id2}")
async def diff_versions(
    event_id: UUID,
    version_id1: UUID,
    version_id2: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a diff between two history versions."""
    await get_event(db, current_user.id, event_id)
    diff = await get_diff_between_versions(db, version_id1, version_id2)
    logger.info(
        "User %s requested diff between versions %s and %s for event %s",
        current_user.username,
        version_id1,
        version_id2,
        event_id,
    )
    return diff
