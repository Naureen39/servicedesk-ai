"""LLM router (Section 4.4): primary/fallback order, automatic failover on HTTP 429, 5xx, or
timeout; a per-provider circuit breaker that opens for 60s after 3 consecutive failures; and a
quota tracker (`llm_usage_daily`) that switches provider proactively at 90% of the configured
daily budget. All limits come from settings, never hardcoded (Section 4.4, last bullet).
"""

from __future__ import annotations

import time
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.assistant import LlmUsageDaily
from app.services.llm.base import LLMProvider, LLMResult, Message, ProviderError

CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_OPEN_SECONDS = 60.0


class AllProvidersUnavailableError(Exception):
    """Raised when every provider in the fallback chain failed, is circuit-open, or is over
    its daily budget. The dialog manager catches this and falls back to a deterministic
    response plus escalation (Section 4.3: "LLM providers both unavailable")."""


class _CircuitBreaker:
    def __init__(self) -> None:
        self.consecutive_failures = 0
        self.open_until: float = 0.0

    def is_open(self) -> bool:
        return time.monotonic() < self.open_until

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.open_until = 0.0

    def record_failure(self, retry_after_s: float | None = None) -> None:
        self.consecutive_failures += 1
        if retry_after_s:
            self.open_until = max(self.open_until, time.monotonic() + retry_after_s)
        if self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            self.open_until = max(self.open_until, time.monotonic() + CIRCUIT_BREAKER_OPEN_SECONDS)


class LLMRouter:
    def __init__(self, providers: dict[str, LLMProvider], order: list[str] | None = None) -> None:
        settings = get_settings()
        self.providers = providers
        self.order = order or self._default_order(settings.llm_primary)
        self._breakers: dict[str, _CircuitBreaker] = {name: _CircuitBreaker() for name in providers}
        self._daily_budgets = {
            "groq": settings.llm_daily_request_budget_groq,
            "gemini": settings.llm_daily_request_budget_gemini,
        }

    def _default_order(self, primary: str) -> list[str]:
        names = list(self.providers.keys())
        if primary in names:
            names.remove(primary)
            names.insert(0, primary)
        return names

    async def _requests_today(self, db: AsyncSession, provider_name: str) -> int:
        result = await db.execute(
            select(LlmUsageDaily.request_count).where(
                LlmUsageDaily.day == date.today(), LlmUsageDaily.provider == provider_name
            )
        )
        row = result.scalar_one_or_none()
        return row or 0

    async def _over_budget(self, db: AsyncSession, provider_name: str) -> bool:
        budget = self._daily_budgets.get(provider_name)
        if not budget:
            return False
        used = await self._requests_today(db, provider_name)
        return used >= 0.9 * budget

    async def _record_usage(self, db: AsyncSession, provider_name: str, result: LLMResult) -> None:
        existing = await db.execute(
            select(LlmUsageDaily).where(LlmUsageDaily.day == date.today(), LlmUsageDaily.provider == provider_name)
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = LlmUsageDaily(day=date.today(), provider=provider_name, request_count=0, tokens_in=0, tokens_out=0)
            db.add(row)
        row.request_count += 1
        row.tokens_in += result.tokens_in
        row.tokens_out += result.tokens_out
        await db.commit()

    async def generate(
        self,
        db: AsyncSession,
        messages: list[Message],
        max_tokens: int,
        json_schema: dict | None = None,
        timeout_s: float = 8.0,
    ) -> LLMResult:
        last_error: Exception | None = None

        for provider_name in self.order:
            provider = self.providers[provider_name]
            breaker = self._breakers[provider_name]

            if not getattr(provider, "is_configured", True):
                continue
            if breaker.is_open():
                continue
            if await self._over_budget(db, provider_name):
                continue

            try:
                result = await provider.generate(messages, max_tokens, json_schema, timeout_s)
            except ProviderError as exc:
                last_error = exc
                breaker.record_failure(exc.retry_after_s)
                continue
            except Exception as exc:  # pragma: no cover - unexpected provider bug
                last_error = exc
                breaker.record_failure()
                continue

            breaker.record_success()
            await self._record_usage(db, provider_name, result)
            return result

        raise AllProvidersUnavailableError(
            f"No LLM provider available (last error: {last_error})"
        ) from last_error
