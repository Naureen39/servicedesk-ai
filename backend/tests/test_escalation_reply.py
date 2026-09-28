"""Regression test: POST /escalations/{id}/reply used to build its message id as
f"MSG-{escalation_id}-{turn:03d}" -- since a real escalation_id is always
"ESC-" + 10 hex chars (app/services/dialog/policy.py), that reply id is 22+ characters
against a messages.message_id column that is VARCHAR(20), so every real reply 500'd with a
StringDataRightTruncationError. Every other message id in the app uses a short random-hex
form instead (app/services/dialog/manager.py, app/api/v1/public.py); the reply endpoint now
matches that.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models.assistant import Conversation, Message
from app.services.dialog.manager import handle_turn

from .conftest import create_user, login

pytestmark = pytest.mark.asyncio


async def _create_open_escalation() -> str:
    conversation_id = f"CONV-{uuid.uuid4().hex[:10].upper()}"
    async with async_session_factory() as db:
        conv = Conversation(conversation_id=conversation_id, channel="chat", started_at=datetime.now(UTC), location_id=1)
        db.add(conv)
        await db.commit()
        result = await handle_turn(db, conv, "I smell smoke coming from the engine right now", None, channel="chat")
        assert result.escalate_reason == "safety_concern", result.text
        refreshed = await db.execute(select(Conversation).where(Conversation.conversation_id == conversation_id))
        conv = refreshed.scalar_one()

    from app.db.models.assistant import Escalation

    async with async_session_factory() as db:
        esc = (await db.execute(select(Escalation).where(Escalation.conversation_id == conversation_id))).scalar_one()
        return esc.escalation_id


async def test_reply_to_a_real_escalation_succeeds(client, auth_headers):
    escalation_id = await _create_open_escalation()
    assert len(escalation_id) == 14, f"escalation ids are expected to be ESC- + 10 hex chars, got {escalation_id!r}"

    advisor = await create_user("advisor-reply-test@example.com", "correct-password-1", "service_advisor", location_id=1)
    token = await login(client, advisor.email, "correct-password-1")

    resp = await client.post(
        f"/api/v1/escalations/{escalation_id}/reply",
        json={"text": "Advised customer to pull over safely; dispatched a tow."},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    message_id = resp.json()["message_id"]
    assert len(message_id) <= 20, f"message_id {message_id!r} exceeds the messages.message_id VARCHAR(20) column"

    async with async_session_factory() as db:
        message = (await db.execute(select(Message).where(Message.message_id == message_id))).scalar_one()
        assert message.sender == "advisor"
        assert message.text == "Advised customer to pull over safely; dispatched a tow."
