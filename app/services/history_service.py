# app/services/history_service.py

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import jsondiff
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event import Event
from app.models.history import History
from app.utils.exceptions import NotFoundError, ServiceUnavailableError

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")


async def get_event_history_versions(db: AsyncSession, event_id: UUID) -> List[History]:
    """
    Retrieve all history versions for the specified event ordered by version ascending.
    """
    try:
        stmt = (
            select(History)
            .where(History.event_id == event_id)
            .order_by(History.version)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as exc:
        logger.error(
            "Error fetching history versions for event %s: %s",
            event_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError("Database temporarily unavailable")


async def get_event_version(db: AsyncSession, version_id: UUID) -> Optional[History]:
    """
    Retrieve a specific history version by its ID.
    """
    try:
        stmt = select(History).where(History.id == version_id)
        result = await db.execute(stmt)
        return result.scalars().first()
    except Exception as exc:
        logger.error(
            "Error fetching history version %s: %s", version_id, exc, exc_info=True
        )
        raise ServiceUnavailableError("Database temporarily unavailable")


async def rollback_event_to_version(
    db: AsyncSession, event_id: UUID, version_id: UUID, user_id: UUID
) -> Event:
    """
    Roll back an event to a specified history version.
    Also saves the current event state as a new history version before rollback.
    """
    try:
        version = await get_event_version(db, version_id)
        if not version:
            logger.warning("Rollback failed: version %s not found", version_id)
            raise NotFoundError("Version not found")

        stmt = select(Event).where(Event.id == event_id)
        result = await db.execute(stmt)
        event = result.scalars().first()
        if not event:
            logger.warning("Rollback failed: event %s not found", event_id)
            raise NotFoundError("Event not found")

        # Apply the snapshot data to the event
        data = version.data
        for field in [
            "title",
            "description",
            "start_time",
            "end_time",
            "location",
            "is_recurring",
            "recurrence_pattern",
        ]:
            value = data.get(field)
            if value is not None:
                # Convert ISO string back to datetime if necessary
                if field in ("start_time", "end_time") and isinstance(value, str):
                    value = datetime.fromisoformat(value)
                setattr(event, field, value)

        # Determine next version number for history
        version_stmt = (
            select(History.version)
            .where(History.event_id == event_id)
            .order_by(History.version.desc())
            .limit(1)
        )
        last_version_result = await db.execute(version_stmt)
        last_version = last_version_result.scalars().first()
        next_version = 1 if last_version is None else last_version + 1

        # Create a snapshot of current event state
        current_snapshot = {
            "title": event.title,
            "description": event.description,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
            "location": event.location,
            "is_recurring": event.is_recurring,
            "recurrence_pattern": event.recurrence_pattern,
            "owner_id": str(event.owner_id),
        }
        history = History(
            event_id=event_id,
            version=next_version,
            data=current_snapshot,
            timestamp=datetime.utcnow(),
            changed_by=user_id,
        )
        db.add(history)

        await db.commit()

        # !! ГЛАВНОЕ: Загрузить event со всеми нужными связями для сериализации
        stmt = (
            select(Event)
            .options(selectinload(Event.permissions))
            .where(Event.id == event_id)
        )
        result = await db.execute(stmt)
        event = result.scalars().first()
        if not event:
            raise NotFoundError("Event not found after rollback")

        logger.info(
            "Rolled back event %s to version %s by user %s",
            event_id,
            version_id,
            user_id,
        )
        audit_logger.info(
            "Event rollback: event_id=%s to version=%s by user=%s",
            event_id,
            version_id,
            user_id,
        )

        return event

    except Exception as exc:
        await db.rollback()
        logger.error(
            "Error rolling back event %s to version %s: %s",
            event_id,
            version_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError("Database temporarily unavailable")


async def get_diff_between_versions(
    db: AsyncSession, version_id1: UUID, version_id2: UUID
):
    """
    Compute a JSON diff between two event history versions.
    """
    try:
        v1 = await get_event_version(db, version_id1)
        v2 = await get_event_version(db, version_id2)
        if not v1 or not v2:
            logger.warning(
                "Diff failed: version(s) %s or %s not found", version_id1, version_id2
            )
            raise NotFoundError("Version not found")

        diff = jsondiff.diff(v1.data, v2.data)
        logger.debug(
            "Computed diff between versions %s and %s", version_id1, version_id2
        )
        return diff
    except Exception as exc:
        logger.error(
            "Error computing diff between versions %s and %s: %s",
            version_id1,
            version_id2,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError("Database temporarily unavailable")
