"""Assistant tables: conversations, messages, escalations, LLM usage, response cache."""

from __future__ import annotations

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

EMBEDDING_DIM = 384


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.customer_id"))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.location_id"))
    channel: Mapped[str | None] = mapped_column(String(10))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contained: Mapped[bool | None] = mapped_column(Boolean)
    escalated: Mapped[bool | None] = mapped_column(Boolean)
    resulting_appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.appointment_id"))
    intent: Mapped[str | None] = mapped_column(String(50))
    state: Mapped[dict | None] = mapped_column(JSON)
    """Dialog manager state (Section 4.2): current intent, filled slots, pending slot,
    attempt counters, vehicle context, last offered time slots."""
    tokens_used_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    """Running total for the per-conversation hard cap (Section 4.5, item 7: 3,000 tokens)."""


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.conversation_id"), index=True)
    turn: Mapped[int | None] = mapped_column(Integer)
    sender: Mapped[str | None] = mapped_column(String(10))
    text: Mapped[str | None] = mapped_column(String)
    intent: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    slots: Mapped[dict | None] = mapped_column(JSON)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    provider: Mapped[str | None] = mapped_column(String(20))
    cache_hit: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    helpful: Mapped[bool | None] = mapped_column(Boolean)
    """Section 7.5: chat widget thumbs up/down feedback on an assistant message."""


class Escalation(Base):
    __tablename__ = "escalations"
    __table_args__ = (
        Index("ix_escalations_open", "status", postgresql_where="status = 'open'"),
    )

    escalation_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.conversation_id"), index=True)
    reason: Mapped[str | None] = mapped_column(String(50))
    priority: Mapped[str | None] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(20), default="open")
    assigned_to: Mapped[str | None] = mapped_column(String(255))
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str | None] = mapped_column(String)


class LlmUsageDaily(Base):
    __tablename__ = "llm_usage_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)


class ResponseCache(Base):
    __tablename__ = "response_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    question: Mapped[str | None] = mapped_column(String)
    answer: Mapped[str | None] = mapped_column(String)
    intent: Mapped[str | None] = mapped_column(String(50))
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
