# app/utils/notifications.py

import json
import logging
from typing import Any, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws_notifications import NOTIFICATIONS_CHANNEL
from app.db.redis import redis_client
from app.models.permission import Permission

logger = logging.getLogger("app.notifications")


async def get_event_participant_user_ids(event_id: Any, db: AsyncSession) -> List[str]:
    stmt = select(Permission.user_id).where(Permission.event_id == event_id)
    result = await db.execute(stmt)
    user_ids = [str(row[0]) for row in result.all()]
    logger.debug("Participants for event_id=%s: %s", event_id, user_ids)
    return user_ids


async def notify_event_users_for_ids(user_ids: List[str], notification: dict) -> None:
    """
    Отправляет уведомление только заданным user_ids.
    """
    if not user_ids:
        logger.info("No recipients for targeted notification.")
        return
    msg = {
        "user_ids": user_ids,
        "notification": notification,
    }
    try:
        payload = json.dumps(msg)
        await redis_client.publish(NOTIFICATIONS_CHANNEL, payload)
        logger.info(
            "Published targeted notification to users=%s | Payload: %s",
            user_ids,
            notification,
        )
    except Exception as exc:
        logger.error("Failed to publish targeted notification: %s", exc)


async def notify_event_users(
    event_id: Any, notification: dict, db: AsyncSession
) -> None:
    """
    Оставлена для совместимости: рассылает всем с правами на event.
    """
    user_ids = await get_event_participant_user_ids(event_id, db)
    await notify_event_users_for_ids(user_ids, notification)
