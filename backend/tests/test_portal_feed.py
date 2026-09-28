"""Unit tests for the in-process portal WebSocket pub/sub broadcaster (Section 4.3)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.services.dialog import portal_feed

pytestmark = pytest.mark.asyncio


@dataclass
class _FakeEscalation:
    escalation_id: str
    conversation_id: str
    priority: str
    reason: str
    sla_due_at: datetime | None


async def test_subscribers_receive_published_escalations():
    queue = portal_feed.subscribe()
    try:
        escalation = _FakeEscalation(
            escalation_id="esc-1",
            conversation_id="conv-1",
            priority="high",
            reason="safety",
            sla_due_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        await portal_feed.publish_escalation(escalation)

        event = queue.get_nowait()
        assert event["type"] == "escalation.created"
        assert event["escalation_id"] == "esc-1"
        assert event["priority"] == "high"
        assert event["sla_due_at"] == "2026-01-01T00:00:00+00:00"
    finally:
        portal_feed.unsubscribe(queue)


async def test_publish_escalation_handles_no_sla_due_at():
    queue = portal_feed.subscribe()
    try:
        escalation = _FakeEscalation(
            escalation_id="esc-2", conversation_id="conv-2", priority="low", reason="question", sla_due_at=None
        )
        await portal_feed.publish_escalation(escalation)

        event = queue.get_nowait()
        assert event["sla_due_at"] is None
    finally:
        portal_feed.unsubscribe(queue)


async def test_unsubscribed_queue_receives_nothing_further():
    queue = portal_feed.subscribe()
    portal_feed.unsubscribe(queue)

    await portal_feed._publish({"type": "noop"})

    assert queue.empty()


async def test_publish_does_not_raise_when_a_subscriber_queue_is_full():
    queue = portal_feed.subscribe()
    try:
        for _ in range(queue.maxsize):
            queue.put_nowait({"type": "filler"})

        await portal_feed._publish({"type": "overflow"})
    finally:
        portal_feed.unsubscribe(queue)


async def test_unsubscribe_is_a_no_op_for_an_unknown_queue():
    portal_feed.unsubscribe(asyncio.Queue())
