from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.db.base import async_session_factory
from app.db.models.assistant import Conversation
from app.services.dialog.manager import handle_turn

pytestmark = pytest.mark.asyncio


async def _new_conversation(db, conversation_id: str) -> Conversation:
    conv = Conversation(conversation_id=conversation_id, channel="chat", started_at=datetime.now(UTC))
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def test_greeting_is_templated_and_contained():
    async with async_session_factory() as db:
        conv = await _new_conversation(db, "CONV-SMOKE-1")
        result = await handle_turn(db, conv, "hi there", router=None)
    assert result.contained is True
    assert "Meridian" in result.text


async def test_pricing_estimate_flow():
    async with async_session_factory() as db:
        conv = await _new_conversation(db, "CONV-SMOKE-2")
        result = await handle_turn(db, conv, "how much does an oil change cost", router=None)
    assert "$" in result.text
