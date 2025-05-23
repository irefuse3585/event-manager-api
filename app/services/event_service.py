import logging
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import PermissionRole
from app.models.event import Event
from app.models.permission import Permission
from app.utils.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
)

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")


async def get_user_event_permission(
    db: AsyncSession, user_id: uuid.UUID, event_id: uuid.UUID
) -> Optional[Permission]:
    """Return Permission for a user and event, or None if not found."""
    try:
        stmt = select(Permission).where(
            Permission.user_id == user_id, Permission.event_id == event_id
        )
        result = await db.execute(stmt)
        return result.scalars().first()
    except SQLAlchemyError as exc:
        logger.error("DB error in get_user_event_permission: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")


async def create_event(db: AsyncSession, user_id: uuid.UUID, data: dict) -> Event:
    """Create a new event with time overlap detection."""
    try:
        # Conflict detection
        stmt = (
            select(Event)
            .where(Event.owner_id == user_id)
            .where(Event.start_time < data["end_time"])
            .where(Event.end_time > data["start_time"])
        )
        overlapping = await db.execute(stmt)
        if overlapping.scalars().first():
            raise ConflictError("Event time overlaps with existing event")

        # Create event + owner permission
        event = Event(**data, owner_id=user_id)
        db.add(event)
        await db.flush()

        perm = Permission(user_id=user_id, event_id=event.id, role=PermissionRole.OWNER)
        db.add(perm)

        await db.commit()
        await db.refresh(event)

        # Load permissions
        stmt = (
            select(Event)
            .options(selectinload(Event.permissions))
            .where(Event.id == event.id)
        )
        result = await db.execute(stmt)
        created = result.scalars().first()
        if not created:
            raise NotFoundError("Event not found after creation")

        logger.info("Event created: id=%s by user=%s", created.id, user_id)
        audit_logger.info("Event created: id=%s by user=%s", created.id, user_id)
        return created

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("DB error during event creation: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")


async def create_events_batch(
    db: AsyncSession, user_id: uuid.UUID, data_list: List[dict]
) -> List[Event]:
    """Create multiple events atomically (all-or-nothing)."""
    created: List[Event] = []
    try:
        for data in data_list:
            stmt = (
                select(Event)
                .where(Event.owner_id == user_id)
                .where(Event.start_time < data["end_time"])
                .where(Event.end_time > data["start_time"])
            )
            overlapping = await db.execute(stmt)
            if overlapping.scalars().first():
                raise ConflictError(
                    f"Event time overlaps with existing event: {data.get('title')}"
                )

            event = Event(**data, owner_id=user_id)
            db.add(event)
            await db.flush()

            perm = Permission(
                user_id=user_id, event_id=event.id, role=PermissionRole.OWNER
            )
            db.add(perm)

            created.append(event)

        await db.commit()

        # Refresh all and load permissions
        for ev in created:
            await db.refresh(ev)

        stmt = (
            select(Event)
            .options(selectinload(Event.permissions))
            .where(Event.id.in_([e.id for e in created]))
        )
        result = await db.execute(stmt)
        events_with_perms = list(result.scalars().all())

        logger.info(
            "Batch event creation: count=%d by user=%s", len(events_with_perms), user_id
        )
        audit_logger.info(
            "Batch event creation: count=%d by user=%s", len(events_with_perms), user_id
        )
        return events_with_perms

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("DB error during batch event creation: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")


async def get_event(db: AsyncSession, user_id: uuid.UUID, event_id: uuid.UUID) -> Event:
    """Return event if user has permission."""
    try:
        stmt = (
            select(Event)
            .options(selectinload(Event.permissions))
            .where(Event.id == event_id)
        )
        result = await db.execute(stmt)
        event = result.scalars().first()
    except SQLAlchemyError as exc:
        logger.error("DB error during event get: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")

    if not event:
        raise NotFoundError("Event not found")

    perm = await get_user_event_permission(db, user_id, event_id)
    if not perm:
        raise ForbiddenError("You do not have access to this event")

    return event


async def list_events(
    db: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> List[Event]:
    """List all events accessible by the user."""
    try:
        stmt = (
            select(Event)
            .join(Permission, Permission.event_id == Event.id)
            .options(selectinload(Event.permissions))
            .where(Permission.user_id == user_id)
            .order_by(Event.start_time)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except SQLAlchemyError as exc:
        logger.error("DB error during events listing: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")


async def update_event(
    db: AsyncSession, user_id: uuid.UUID, event_id: uuid.UUID, data: dict
) -> Event:
    """Update event (OWNER/EDITOR), checking for time overlap."""
    perm = await get_user_event_permission(db, user_id, event_id)
    if not perm or perm.role not in (
        PermissionRole.OWNER,
        PermissionRole.EDITOR,
    ):
        raise ForbiddenError("You do not have permission to update this event")

    try:
        # Conflict detection
        if "start_time" in data and "end_time" in data:
            stmt = (
                select(Event)
                .where(Event.owner_id == user_id)
                .where(Event.id != event_id)
                .where(Event.start_time < data["end_time"])
                .where(Event.end_time > data["start_time"])
            )
            overlapping = await db.execute(stmt)
            if overlapping.scalars().first():
                raise ConflictError("Event time overlaps with existing event")

        # Load, update, commit
        stmt = (
            select(Event)
            .options(selectinload(Event.permissions))
            .where(Event.id == event_id)
        )
        result = await db.execute(stmt)
        event = result.scalars().first()
        if not event:
            raise NotFoundError("Event not found")

        for field, val in data.items():
            setattr(event, field, val)

        await db.commit()
        await db.refresh(event)

        logger.info("Event updated: id=%s by user=%s", event_id, user_id)
        audit_logger.info("Event updated: id=%s by user=%s", event_id, user_id)
        return event

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("DB error during event update: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")


async def delete_event(db: AsyncSession, user_id: uuid.UUID, event_id: uuid.UUID):
    """Delete event (OWNER only)."""
    # 1) Attempt to load the event from the database
    try:
        stmt = (
            select(Event)
            .options(selectinload(Event.permissions))
            .where(Event.id == event_id)
        )
        result = await db.execute(stmt)
        event = result.scalars().first()
    except SQLAlchemyError as exc:
        # If any database error occurs during lookup, abort with 503
        logger.error("DB error during event lookup: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")

    # 2) If the event does not exist, return 404
    if not event:
        raise NotFoundError("Event not found")

    # 3) Check that the user holds OWNER permission on this event
    perm = await get_user_event_permission(db, user_id, event_id)
    if not perm or perm.role != PermissionRole.OWNER:
        # User is not authorized to delete this event
        raise ForbiddenError("You do not have permission to delete this event")

    # 4) Proceed to delete the event and commit the transaction
    try:
        await db.delete(event)
        await db.commit()
        logger.info("Event deleted: id=%s by user=%s", event_id, user_id)
        audit_logger.info("Event deleted: id=%s by user=%s", event_id, user_id)
    except SQLAlchemyError as exc:
        # Roll back if deletion fails
        await db.rollback()
        logger.error("DB error during event delete: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")
