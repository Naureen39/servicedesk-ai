from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TurnResult:
    text: str
    contained: bool = True
    escalate_reason: str | None = None
    llm_provider: str | None = None
    llm_tokens_in: int = 0
    llm_tokens_out: int = 0
    cache_hit: bool = False
    flow_complete: bool = True
    """False while a multi-turn flow (like booking) is still collecting slots."""
    message_id: str | None = None
    """Set by `_finalize` after logging the assistant's reply; lets a caller (the chat REST
    endpoint) return an id thumbs-up/down feedback can reference (Section 7.5)."""
