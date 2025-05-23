# app/services/permission_service.py

import logging
import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PermissionRole
from app.models.permission import Permission
from app.services.event_service import get_user_event_permission
from app.utils.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
)

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")


async def list_permissions(
    db: AsyncSession, current_user_id: uuid.UUID, event_id: uuid.UUID
) -> List[Permission]:
    """Return all permissions on event if current_user has at least VIEWER."""
    # Check access
    perm = await get_user_event_permission(db, current_user_id, event_id)
    if not perm:
        raise ForbiddenError("You do not have access to this event")
    try:
        stmt = select(Permission).where(Permission.event_id == event_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except SQLAlchemyError as exc:
        logger.error("DB error in list_permissions: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")


async def update_permission(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    event_id: uuid.UUID,
    target_user_id: uuid.UUID,
    new_role: str,
) -> Permission:
    """Change role for a single user. Only OWNER."""
    owner_perm = await get_user_event_permission(db, current_user_id, event_id)
    if not owner_perm or owner_perm.role != PermissionRole.OWNER:
        raise ForbiddenError("Only owner can update permissions")
    try:
        stmt = select(Permission).where(
            Permission.event_id == event_id,
            Permission.user_id == target_user_id,
        )
        result = await db.execute(stmt)
        perm = result.scalars().first()
    except SQLAlchemyError as exc:
        logger.error("DB error fetching permission: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")
    if not perm:
        raise NotFoundError("Permission not found")
    if perm.user_id == current_user_id:
        raise ConflictError("Cannot change owner's own permission")
    try:
        perm.role = PermissionRole(new_role)
        await db.commit()
        await db.refresh(perm)
        logger.info(
            "Permission updated on event %s for user %s by user %s",
            event_id,
            target_user_id,
            current_user_id,
        )
        audit_logger.info(
            "Permission updated on event %s for user %s by user %s",
            event_id,
            target_user_id,
            current_user_id,
        )
        return perm
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("DB error updating permission: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")


async def delete_permission(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    event_id: uuid.UUID,
    target_user_id: uuid.UUID,
):
    """Revoke a user's access. Only OWNER."""
    owner_perm = await get_user_event_permission(db, current_user_id, event_id)
    if not owner_perm or owner_perm.role != PermissionRole.OWNER:
        raise ForbiddenError("Only owner can delete permissions")
    try:
        stmt = select(Permission).where(
            Permission.event_id == event_id,
            Permission.user_id == target_user_id,
        )
        result = await db.execute(stmt)
        perm = result.scalars().first()
    except SQLAlchemyError as exc:
        logger.error("DB error fetching permission: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")
    if not perm:
        raise NotFoundError("Permission not found")
    try:
        await db.delete(perm)
        await db.commit()
        logger.info(
            "Permission deleted on event %s for user %s by user %s",
            event_id,
            target_user_id,
            current_user_id,
        )
        audit_logger.info(
            "Permission deleted on event %s for user %s by user %s",
            event_id,
            target_user_id,
            current_user_id,
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("DB error deleting permission: %s", exc, exc_info=True)
        raise ServiceUnavailableError("Database temporarily unavailable")
