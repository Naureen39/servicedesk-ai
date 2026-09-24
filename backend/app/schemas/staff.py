from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationOut(BaseModel):
    conversation_id: str
    customer_id: str | None
    location_id: int | None
    channel: str | None
    started_at: datetime | None
    ended_at: datetime | None
    contained: bool | None
    escalated: bool | None
    intent: str | None

    model_config = ConfigDict(from_attributes=True)


class MessageOut(BaseModel):
    message_id: str
    conversation_id: str
    turn: int | None
    sender: str | None
    text: str | None
    intent: str | None
    confidence: float | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class EscalationOut(BaseModel):
    escalation_id: str
    conversation_id: str
    reason: str | None
    priority: str | None
    status: str
    assigned_to: str | None
    sla_due_at: datetime | None
    created_at: datetime | None
    resolved_at: datetime | None
    summary: str | None

    model_config = ConfigDict(from_attributes=True)


class EscalationPatch(BaseModel):
    status: str | None = None
    assigned_to: str | None = None


class EscalationReplyRequest(BaseModel):
    text: str
