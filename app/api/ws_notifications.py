# app/api/ws_notifications.py

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.redis import redis_client
from app.utils.deps import get_current_user_ws  # Новая зависимость

router = APIRouter()
logger = logging.getLogger("app.ws_notifications")

active_ws_connections: dict[str, set[WebSocket]] = {}


async def register_ws(user_id: str, ws: WebSocket):
    conns = active_ws_connections.setdefault(user_id, set())
    conns.add(ws)
    logger.debug(
        "Registered WS for user_id=%s, total connections=%d", user_id, len(conns)
    )


async def unregister_ws(user_id: str, ws: WebSocket):
    conns = active_ws_connections.get(user_id)
    if conns:
        conns.discard(ws)
        logger.debug(
            "Unregistered WS for user_id=%s, remaining=%d", user_id, len(conns)
        )
        if not conns:
            del active_ws_connections[user_id]
            logger.debug("Removed all WS for user_id=%s", user_id)


@router.websocket("/api/ws/notifications")
async def ws_notifications(websocket: WebSocket):
    # Получаем пользователя через новую функцию
    user = await get_current_user_ws(websocket)
    await websocket.accept()
    user_id = str(user.id)
    await register_ws(user_id, websocket)
    logger.info("WS connected: user=%s", user_id)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await unregister_ws(user_id, websocket)
        logger.info("WS disconnected: user=%s", user_id)
    except Exception as exc:
        await unregister_ws(user_id, websocket)
        logger.exception("WS error for user=%s: %s", user_id, exc)


NOTIFICATIONS_CHANNEL = "event_notifications"


async def redis_listener():
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(NOTIFICATIONS_CHANNEL)
    logger.info("Started Redis notifications listener")
    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1
            )
            if message:
                try:
                    payload = json.loads(message["data"])
                    user_ids = payload["user_ids"]
                    notification = payload["notification"]
                    logger.debug(
                        "Dispatching notification to users: %s; payload: %s",
                        user_ids,
                        notification,
                    )
                    await _send_ws_notifications(user_ids, notification)
                except Exception as e:
                    logger.error(
                        "Error parsing notification payload: %s | Raw message: %s",
                        e,
                        message,
                    )
            await asyncio.sleep(0.01)
    finally:
        await pubsub.unsubscribe(NOTIFICATIONS_CHANNEL)
        await pubsub.close()
        logger.info("Redis notifications listener stopped")


async def _send_ws_notifications(user_ids, notification):
    to_remove = []
    for user_id in user_ids:
        conns = active_ws_connections.get(user_id)
        if conns:
            to_remove_ws = set()
            for ws in conns:
                try:
                    await ws.send_json(notification)
                    logger.info(
                        "Notification sent to user_id=%s: %s", user_id, notification
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to send notification to user_id=%s: %s", user_id, exc
                    )
                    to_remove_ws.add(ws)
            for ws in to_remove_ws:
                conns.discard(ws)
            if not conns:
                to_remove.append(user_id)
    for user_id in to_remove:
        active_ws_connections.pop(user_id, None)
        logger.debug("Removed empty connection pool for user_id=%s", user_id)
