# app/api/permissions.py

import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.permission import PermissionRead, PermissionUpdate
from app.services.permission_service import (
    delete_permission,
    list_permissions,
    update_permission,
)
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/events/{event_id}/permissions", tags=["permissions"])
logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")


@router.get("", response_model=List[PermissionRead])
async def read_permissions(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    List all permissions on the event.
    """
    perms = await list_permissions(db, current_user.id, event_id)
    return [PermissionRead.from_orm(p) for p in perms]


@router.put("/{user_id}", response_model=PermissionRead)
async def change_permission(
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    upd: PermissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Update a single user's permission. Only OWNER may call.
    """
    perm = await update_permission(
        db, current_user.id, event_id, user_id, upd.role.value
    )
    return PermissionRead.from_orm(perm)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_permission(
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Revoke a user's access. Only OWNER may call.
    """
    await delete_permission(db, current_user.id, event_id, user_id)
