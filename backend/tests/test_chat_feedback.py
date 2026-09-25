"""Phase 7: the chat widget's thumbs up/down needs a real message_id round trip --
POST /chat/message now returns the assistant message's id, and POST /chat/feedback persists
helpful/unhelpful onto that exact row (previously a no-op stub)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models.assistant import Message
from app.main import app

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac


async def test_message_response_includes_message_id_and_feedback_persists(client):
    session_resp = await client.post("/api/v1/chat/session")
    assert session_resp.status_code == 200
    session = session_resp.json()
    headers = {"Authorization": f"Bearer {session['session_token']}"}

    msg_resp = await client.post(
        "/api/v1/chat/message",
        json={"conversation_id": session["conversation_id"], "text": "hi there"},
        headers=headers,
    )
    assert msg_resp.status_code == 200
    body = msg_resp.json()
    assert body["message_id"]

    feedback_resp = await client.post(
        "/api/v1/chat/feedback",
        json={"conversation_id": session["conversation_id"], "message_id": body["message_id"], "helpful": True},
        headers=headers,
    )
    assert feedback_resp.status_code == 204

    async with async_session_factory() as db:
        result = await db.execute(select(Message).where(Message.message_id == body["message_id"]))
        message = result.scalar_one()
    assert message.helpful is True


async def test_feedback_on_unknown_message_404s(client):
    session_resp = await client.post("/api/v1/chat/session")
    session = session_resp.json()
    headers = {"Authorization": f"Bearer {session['session_token']}"}

    resp = await client.post(
        "/api/v1/chat/feedback",
        json={"conversation_id": session["conversation_id"], "message_id": "MSG-DOESNOTEXIST", "helpful": False},
        headers=headers,
    )
    assert resp.status_code == 404
