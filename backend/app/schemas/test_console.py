from __future__ import annotations

from pydantic import BaseModel


class TestConsoleRequest(BaseModel):
    conversation_id: str | None = None
    text: str


class RetrievedChunkOut(BaseModel):
    title: str | None
    section: str | None
    content: str
    similarity: float


class TestConsoleResponse(BaseModel):
    conversation_id: str
    reply_text: str
    escalated: bool
    intent: str | None
    confidence: float | None
    slots: dict
    retrieved_chunks: list[RetrievedChunkOut]
    provider: str | None
    tokens_in: int
    tokens_out: int
    cache_hit: bool
    latency_ms: int
