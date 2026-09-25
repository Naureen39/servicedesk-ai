"""In-process pub/sub broadcasting escalations (and, later, live conversation events) to every
connected `/portal/live` WebSocket (Section 4.3: "push it to staff via WebSocket"). A single
process's in-memory broadcaster is sufficient for this deployment shape (one API process
behind Caddy per Section 3.2's infra); a multi-process deployment would swap this for a
Postgres LISTEN/NOTIFY or Redis pub/sub without changing the publish/subscribe call sites.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

_subscribers: set[asyncio.Queue] = set()


def subscribe() -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(queue)
    return queue


def unsubscribe(queue: asyncio.Queue) -> None:
    _subscribers.discard(queue)


async def _publish(event: dict[str, Any]) -> None:
    for queue in list(_subscribers):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def publish_escalation(escalation) -> None:
    await _publish(
        {
            "type": "escalation.created",
            "escalation_id": escalation.escalation_id,
            "conversation_id": escalation.conversation_id,
            "priority": escalation.priority,
            "reason": escalation.reason,
            "sla_due_at": escalation.sla_due_at.isoformat() if escalation.sla_due_at else None,
            "timestamp": datetime.now().isoformat(),
        }
    )
