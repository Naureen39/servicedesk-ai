"""Phase 8 Assistant Test Console: runs the real dialog pipeline and returns the debug panel
fields (intent, confidence, slots, retrieved chunks, provider, tokens, latency) a staff member
uses for client demos."""

from __future__ import annotations

import pytest

from .conftest import create_user, login

pytestmark = pytest.mark.asyncio


async def test_console_returns_real_debug_fields(client, auth_headers):
    advisor = await create_user("advisor-console@example.com", "pw", "service_advisor", mfa=False)
    token = await login(client, advisor.email, "pw")

    resp = await client.post(
        "/api/v1/test-console/message",
        json={"text": "I need to book an oil change"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["conversation_id"]
    assert body["intent"] == "book_service"
    assert body["confidence"] is not None
    assert body["latency_ms"] >= 0
    assert isinstance(body["retrieved_chunks"], list)
    assert "vehicle" in body["reply_text"].lower() or "year" in body["reply_text"].lower()


async def test_console_continues_the_same_conversation(client, auth_headers):
    advisor = await create_user("advisor-console2@example.com", "pw", "service_advisor", mfa=False)
    token = await login(client, advisor.email, "pw")
    headers = auth_headers(token)

    first = await client.post("/api/v1/test-console/message", json={"text": "how long is my powertrain warranty"}, headers=headers)
    assert first.status_code == 200
    conv_id = first.json()["conversation_id"]

    second = await client.post(
        "/api/v1/test-console/message",
        json={"conversation_id": conv_id, "text": "thanks"},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conv_id


async def test_console_requires_permission(client, auth_headers):
    analyst = await create_user("analyst-console@example.com", "pw", "analyst", mfa=False)
    token = await login(client, analyst.email, "pw")
    resp = await client.post("/api/v1/test-console/message", json={"text": "hello"}, headers=auth_headers(token))
    assert resp.status_code == 403
