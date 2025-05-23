# app/services/event_service.py

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import PermissionRole
from app.models.event import Event
from app.models.history import History
from app.models.permission import Permission
from app.utils.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.utils.notifications import (
    get_event_participant_user_ids,
    notify_event_users_for_ids,
)

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")


def to_uuid(x):
    if isinstance(x, uuid.UUID):
        return x
    elif isinstance(x, str):
        return uuid.UUID(x)
    elif hasattr(x, "__uuid__"):
        return uuid.UUID(str(x))
    else:
        return uuid.UUID(str(x))


async def get_user_event_permission(
    db: AsyncSession, user_id, event_id
) -> Optional[Permission]:
    """Return Permission for a user and event, or None if not found."""
    user_id = to_uuid(user_id)
    event_id = to_uuid(event_id)
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
        # Conflict detection for overlapping events
        stmt = (
            select(Event)
            .where(Event.owner_id == user_id)
            .where(Event.start_time < data["end_time"])
            .where(Event.end_time > data["start_time"])
        )
        overlapping = await db.execute(stmt)
        if overlapping.scalars().first():
            raise ConflictError("Event time overlaps with existing event")

        # Create event and add owner permission
        event = Event(**data, owner_id=user_id)
        db.add(event)
        await db.flush()

        perm = Permission(user_id=user_id, event_id=event.id, role=PermissionRole.OWNER)
        db.add(perm)
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
            event_id=event.id,
            version=1,
            data=current_snapshot,
            timestamp=datetime.utcnow(),
            changed_by=user_id,
        )
        db.add(history)
        await db.commit()
        await db.refresh(event)

        # Load permissions (for response consistency)
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
        # No WS notifications — only creator has access at creation time
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
        # No WS notifications — only creator has access at creation time
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
    """
    Update event if user has permission.
    Before updating, save current event data as a new History version with attribution.
    """

    # Check permission for update (OWNER or EDITOR)
    perm = await get_user_event_permission(db, user_id, event_id)
    if not perm or perm.role not in (PermissionRole.OWNER, PermissionRole.EDITOR):
        raise ForbiddenError("You do not have permission to update this event")

    try:
        # Check for time conflict if start and end time are updated
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

        # Load event for update
        stmt = (
            select(Event)
            .where(Event.id == event_id)
            .options(selectinload(Event.permissions))
        )
        result = await db.execute(stmt)
        event = result.scalars().first()
        if not event:
            raise NotFoundError("Event not found")

        # Prepare snapshot of current event data (convert datetime to ISO string)
        old_data = {
            "title": event.title,
            "description": event.description,
            "start_time": event.start_time.isoformat(),
            "end_time": event.end_time.isoformat(),
            "location": event.location,
            "is_recurring": event.is_recurring,
            "recurrence_pattern": event.recurrence_pattern,
            "owner_id": str(event.owner_id),
        }

        # Get last version number for this event
        version_stmt = (
            select(History.version)
            .where(History.event_id == event_id)
            .order_by(History.version.desc())
            .limit(1)
        )
        last_version_result = await db.execute(version_stmt)
        last_version = last_version_result.scalars().first()
        next_version = 1 if last_version is None else last_version + 1

        # Save snapshot as new History entry
        history = History(
            event_id=event_id,
            version=next_version,
            data=old_data,
            timestamp=datetime.utcnow(),
            changed_by=user_id,
        )
        db.add(history)

        # Update event with new data
        for field, val in data.items():
            setattr(event, field, val)

        await db.commit()
        await db.refresh(event)

        return event

    except Exception:
        await db.rollback()
        raise ServiceUnavailableError("Database temporarily unavailable")


async def delete_event(db: AsyncSession, user_id: uuid.UUID, event_id: uuid.UUID):
    """
    Delete event (OWNER only).
    Notify all participants except initiator.
    """
    try:
        stmt = (
            select(Event)
            .options(selectinload(Event.permissions))
            .where(Event.id == event_id)
        )
        result = await db.execute(stmt)
        event = result.scalars().first()
    except SQLAlchemyError as exc:
        logger.error("DB error during event lookup: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")

    if not event:
        raise NotFoundError("Event not found")

    perm = await get_user_event_permission(db, user_id, event_id)
    if not perm or perm.role != PermissionRole.OWNER:
        raise ForbiddenError("You do not have permission to delete this event")

    try:
        await db.delete(event)
        await db.commit()
        logger.info("Event deleted: id=%s by user=%s", event_id, user_id)
        audit_logger.info("Event deleted: id=%s by user=%s", event_id, user_id)

        # Notify all participants except initiator
        user_ids = await get_event_participant_user_ids(event_id, db)
        user_ids = [uid for uid in user_ids if uid != str(user_id)]
        notification = {
            "type": "event_deleted",
            "event_id": str(event_id),
            "initiator_id": str(user_id),
            "message": f"Event '{event.title}' deleted by user {user_id}",
        }
        if user_ids:
            await notify_event_users_for_ids(user_ids, notification)

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("DB error during event delete: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")


async def grant_event_permissions(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    event_id: uuid.UUID,
    items: List[dict],
) -> List[Permission]:
    """
    Bulk grant permissions for an event. Only OWNER can grant.
    items: list of dicts with keys "user_id" and "role".
    Notify only new grantees, not the owner/initiator.
    """
    owner_perm = await get_user_event_permission(db, current_user_id, event_id)
    if not owner_perm or owner_perm.role != PermissionRole.OWNER:
        raise ForbiddenError("Only owner can share the event")

    created: List[Permission] = []
    try:
        for data in items:
            uid = data["user_id"]
            role = PermissionRole(data["role"])
            if uid == current_user_id:
                continue
            # Check for duplicate permissions
            stmt = select(Permission).where(
                Permission.event_id == event_id,
                Permission.user_id == uid,
            )
            exists = (await db.execute(stmt)).scalars().first()
            if exists:
                raise ConflictError(f"Permission already exists for user {uid}")
            perm = Permission(user_id=uid, event_id=event_id, role=role)
            db.add(perm)
            created.append(perm)

        await db.commit()
        for p in created:
            await db.refresh(p)

        logger.info(
            "Permissions granted on event %s by user %s", event_id, current_user_id
        )
        audit_logger.info(
            "Permissions granted on event %s by user %s", event_id, current_user_id
        )

        # Notify only new grantees (not the owner)
        for p in created:
            notification = {
                "type": "permission_granted",
                "event_id": str(event_id),
                "initiator_id": str(current_user_id),
                "user_id": str(p.user_id),
                "role": p.role.value,
                "message": f"You have been granted {p.role.value} access to event"
                f"{event_id} by user {current_user_id}",
            }
            await notify_event_users_for_ids([str(p.user_id)], notification)

        return created

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("DB error in grant_event_permissions: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")
