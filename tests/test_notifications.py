# tests/test_notifications.py

import asyncio
import json
import os
import time

import httpx
import pytest
import websockets

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/api/ws/notifications"


def unique_login(prefix):
    ts = str(int(time.time() * 1000))
    return {
        "username": f"{prefix}_{ts}",
        "email": f"{prefix}_{ts}@example.com",
        "password": f"{prefix}_testpass",
    }


async def ensure_user(client, username, email, password):
    """
    Tries to register a new user.
    If user already exists, attempts to log in.
    Returns (user_id, access_token).
    """
    resp = await client.post(
        f"{BASE_URL}/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    if resp.status_code == 201:
        token = resp.json()["access_token"]
        resp2 = await client.get(
            f"{BASE_URL}/me", headers={"Authorization": f"Bearer {token}"}
        )
        user_id = resp2.json()["id"]
        return user_id, token

    # If user already exists, log in
    resp = await client.post(
        f"{BASE_URL}/api/auth/login", json={"username": username, "password": password}
    )
    token = resp.json()["access_token"]
    resp2 = await client.get(
        f"{BASE_URL}/me", headers={"Authorization": f"Bearer {token}"}
    )
    user_id = resp2.json()["id"]
    return user_id, token


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("RUN_E2E_TESTS"), reason="E2E tests skipped unless RUN_E2E_TESTS=1"
)
async def test_ws_notification_on_permission_grant():
    """
    Full e2e test:
    - Register/login as owner and user2.
    - Owner creates event.
    - user2 connects to WS.
    - Owner grants EDITOR permission to user2.
    - user2 receives notification via WS.
    """
    owner_creds = unique_login("ws_owner")
    user2_creds = unique_login("ws_user2")

    async with httpx.AsyncClient() as client:
        # Register or login owner
        owner_id, owner_token = await ensure_user(
            client,
            owner_creds["username"],
            owner_creds["email"],
            owner_creds["password"],
        )
        headers_owner = {"Authorization": f"Bearer {owner_token}"}

        # Register or login user2
        user2_id, user2_token = await ensure_user(
            client,
            user2_creds["username"],
            user2_creds["email"],
            user2_creds["password"],
        )

        # Owner creates an event
        event_data = {
            "title": "WS Test Event",
            "description": "Test for websocket notification",
            "start_time": "2025-06-01T10:00:00+00:00",
            "end_time": "2025-06-01T11:00:00+00:00",
        }
        resp = await client.post(
            f"{BASE_URL}/api/events", json=event_data, headers=headers_owner
        )
        assert resp.status_code == 201
        event_id = resp.json()["id"]

    # user2 opens WebSocket connection and waits for notification
    async def ws_wait_for_notification(token):
        headers = [("Authorization", f"Bearer {token}")]
        async with websockets.connect(WS_URL, additional_headers=headers) as ws:
            message = await ws.recv()
            return json.loads(message)

    ws_task = asyncio.create_task(ws_wait_for_notification(user2_token))
    await asyncio.sleep(0.5)  # Ensure WS is connected

    # Owner grants permission to user2
    async with httpx.AsyncClient() as client:
        payload = [{"user_id": str(user2_id), "role": "Editor"}]
        resp = await client.post(
            f"{BASE_URL}/api/events/{event_id}/share",
            json=payload,
            headers=headers_owner,
        )
        assert resp.status_code == 201

    # user2 should receive a WebSocket notification
    notification = await asyncio.wait_for(ws_task, timeout=5)
    assert notification["type"] == "permission_granted"
    assert notification["event_id"] == event_id
    assert notification["user_id"] == user2_id
