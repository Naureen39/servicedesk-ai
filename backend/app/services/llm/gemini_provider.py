"""Gemini provider (Section 4.4): official `google-genai` SDK, Flash-family model from
config, thinking budget set to the minimum the model allows, temperature 0.2.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.config import get_settings
from app.services.llm.base import LLMProvider, LLMResult, Message, ProviderError


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model or settings.gemini_model

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
            raise ProviderError("Gemini API key not configured", retryable=False)

        from google import genai
        from google.genai import errors as genai_errors
        from google.genai import types

        system_parts = [m.content for m in messages if m.role == "system"]
        turns = [m for m in messages if m.role != "system"]

        client = genai.Client(api_key=self.api_key)
        config = types.GenerateContentConfig(
            system_instruction="\n".join(system_parts) or None,
            max_output_tokens=max_tokens,
            temperature=0.2,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            response_mime_type="application/json" if json_schema else None,
        )
        contents = [
            types.Content(role="user" if m.role == "user" else "model", parts=[types.Part(text=m.content)])
            for m in turns
        ]

        start = time.perf_counter()
        try:
            response = await client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
        except genai_errors.ClientError as exc:
            status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            retryable = status in (429, 500, 502, 503, 504) if status else True
            raise ProviderError(f"Gemini request failed: {exc}", retryable=retryable) from exc
        except TimeoutError as exc:
            raise ProviderError(f"Gemini request timed out: {exc}", retryable=True) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        usage = response.usage_metadata
        return LLMResult(
            text=response.text or "",
            tokens_in=getattr(usage, "prompt_token_count", 0) or 0,
            tokens_out=getattr(usage, "candidates_token_count", 0) or 0,
            provider=self.name,
            latency_ms=latency_ms,
        )
