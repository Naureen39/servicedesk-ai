"""Escalation gate (Section 4.3): escalate when intent confidence stays below 0.55 after one
clarification, the intent is complaint/safety_concern/speak_to_human, sentiment is strongly
negative on two consecutive turns, the same slot fails twice, or both LLM providers are
unavailable. Creates an `escalations` row with priority/SLA and a templated summary, and
notifies the live portal feed (Section "push it to staff via WebSocket").
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assistant import Escalation, Message

PRIORITY_SAFETY = "P1"
PRIORITY_COMPLAINT = "P2"
PRIORITY_OTHER = "P3"

SLA_MINUTES = {
    PRIORITY_SAFETY: 15,
    PRIORITY_COMPLAINT: 120,
    PRIORITY_OTHER: 24 * 60,
}

INTENT_PRIORITY = {
    "safety_concern": PRIORITY_SAFETY,
    "complaint": PRIORITY_COMPLAINT,
    "speak_to_human": PRIORITY_OTHER,
}


def priority_for_reason(reason: str) -> str:
    return INTENT_PRIORITY.get(reason, PRIORITY_OTHER)


async def create_escalation(
    db: AsyncSession,
    *,
    conversation_id: str,
    reason: str,
    vehicle_context: dict | None,
    intent: str | None,
    slots: dict | None,
    last_messages: list[Message],
) -> Escalation:
    priority = priority_for_reason(reason)
    sla_due = datetime.now(UTC) + timedelta(minutes=SLA_MINUTES[priority])

    summary_parts = [f"Reason: {reason}"]
    if intent:
        summary_parts.append(f"Intent: {intent}")
    if vehicle_context:
        vehicle_desc = " ".join(str(v) for v in (vehicle_context.get("year"), vehicle_context.get("make"), vehicle_context.get("model")) if v)
        if vehicle_desc:
            summary_parts.append(f"Vehicle: {vehicle_desc}")
    if slots:
        summary_parts.append(f"Slots: {slots}")
    if last_messages:
        recent = "; ".join(f"{m.sender}: {m.text}" for m in last_messages[-3:] if m.text)
        summary_parts.append(f"Recent messages: {recent}")

    escalation = Escalation(
        escalation_id=f"ESC-{uuid.uuid4().hex[:10].upper()}",
        conversation_id=conversation_id,
        reason=reason,
        priority=priority,
        status="open",
        sla_due_at=sla_due,
        created_at=datetime.now(UTC),
        summary=" | ".join(summary_parts),
    )
    db.add(escalation)
    await db.flush()

    from app.services.dialog.portal_feed import publish_escalation

    await publish_escalation(escalation)

    return escalation


def should_escalate_low_confidence(clarification_attempts: int, confidence: float, confidence_threshold: float = 0.55) -> bool:
    return clarification_attempts >= 1 and confidence < confidence_threshold


def should_escalate_slot_failure(attempt_count: int, max_attempts: int = 2) -> bool:
    return attempt_count >= max_attempts


def should_escalate_sentiment(negative_streak: int) -> bool:
    return negative_streak >= 2


ESCALATING_INTENTS = frozenset({"complaint", "safety_concern", "speak_to_human"})
