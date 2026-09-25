"""Common provider interface (Section 4.4): `generate(messages, max_tokens, json_schema=None)
-> LLMResult(text, tokens_in, tokens_out, provider, latency)`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int
    provider: str
    latency_ms: float


class ProviderError(Exception):
    """Raised for any provider failure the router should treat as failover-worthy
    (HTTP 429, 5xx, or timeout, per Section 4.4)."""

    def __init__(self, message: str, *, retryable: bool, retry_after_s: float | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after_s = retry_after_s


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        max_tokens: int,
        json_schema: dict[str, Any] | None = None,
        timeout_s: float = 8.0,
    ) -> LLMResult: ...
