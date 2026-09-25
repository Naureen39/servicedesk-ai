"""Fake LLM providers for tests: no network calls, no real API keys needed. Used to prove the
router's failover/circuit-breaker logic and the dialog manager's LLM call sites work, without
depending on live Groq/Gemini credentials or burning free-tier quota."""

from __future__ import annotations

from app.services.llm.base import LLMProvider, LLMResult, Message, ProviderError
from app.services.llm.router import LLMRouter


class FakeProvider(LLMProvider):
    def __init__(self, name: str, *, fail: bool = False, retryable: bool = True, canned_text: str = "This is a grounded test answer."):
        self.name = name
        self.is_configured = True
        self.fail = fail
        self.retryable = retryable
        self.canned_text = canned_text
        self.call_count = 0

    async def generate(self, messages: list[Message], max_tokens: int, json_schema=None, timeout_s: float = 8.0) -> LLMResult:
        self.call_count += 1
        if self.fail:
            raise ProviderError(f"{self.name} simulated failure", retryable=self.retryable)
        return LLMResult(text=self.canned_text, tokens_in=120, tokens_out=40, provider=self.name, latency_ms=5.0)


def working_router(canned_text: str = "This is a grounded test answer.") -> LLMRouter:
    groq = FakeProvider("groq", canned_text=canned_text)
    gemini = FakeProvider("gemini", canned_text=canned_text)
    return LLMRouter({"groq": groq, "gemini": gemini}, order=["groq", "gemini"])


def groq_disabled_router(canned_text: str = "This is a grounded test answer.") -> LLMRouter:
    """Groq always fails (simulating a disabled/invalid key manifesting as repeated errors);
    Gemini succeeds. Proves failover completes the flow through the fallback provider."""
    groq = FakeProvider("groq", fail=True, canned_text=canned_text)
    gemini = FakeProvider("gemini", canned_text=canned_text)
    return LLMRouter({"groq": groq, "gemini": gemini}, order=["groq", "gemini"])


def both_disabled_router() -> LLMRouter | None:
    """Both providers unavailable -- the dialog manager treats this the same as no router
    configured at all (Section 4.3: "LLM providers both unavailable")."""
    return None
