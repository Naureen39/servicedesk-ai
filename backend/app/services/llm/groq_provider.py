"""Groq provider (Section 4.4): OpenAI-compatible chat completions endpoint,
model `openai/gpt-oss-20b`, `reasoning_effort="low"`, temperature 0.2.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.llm.base import LLMProvider, LLMResult, Message, ProviderError

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.groq_api_key
        self.model = model or settings.groq_model

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(
        self,
        messages: list[Message],
        max_tokens: int,
        json_schema: dict[str, Any] | None = None,
        timeout_s: float = 8.0,
    ) -> LLMResult:
        if not self.is_configured:
            raise ProviderError("Groq API key not configured", retryable=False)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "reasoning_effort": "low",
        }
        if json_schema is not None:
            payload["response_format"] = {"type": "json_schema", "json_schema": json_schema}

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(
                    GROQ_CHAT_COMPLETIONS_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError(f"Groq request timed out: {exc}", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Groq request failed: {exc}", retryable=True) from exc

        latency_ms = (time.perf_counter() - start) * 1000

        if resp.status_code == 429 or resp.status_code >= 500:
            retry_after = resp.headers.get("retry-after")
            raise ProviderError(
                f"Groq returned {resp.status_code}",
                retryable=True,
                retry_after_s=float(retry_after) if retry_after else None,
            )
        if resp.status_code >= 400:
            raise ProviderError(f"Groq returned {resp.status_code}: {resp.text}", retryable=False)

        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResult(
            text=text,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            provider=self.name,
            latency_ms=latency_ms,
        )
