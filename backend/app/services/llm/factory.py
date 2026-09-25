"""Builds the process-wide LLMRouter from settings (Section 4.4: "Primary and fallback order
from settings")."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.groq_provider import GroqProvider
from app.services.llm.router import LLMRouter

_router: LLMRouter | None = None


def get_router() -> LLMRouter | None:
    """Returns None if no provider is configured at all, so callers can treat "no router" the
    same as "both providers unavailable" (Section 4.3 escalation trigger) without special-casing."""
    global _router
    if _router is not None:
        return _router

    settings = get_settings()
    providers = {"groq": GroqProvider(), "gemini": GeminiProvider()}
    if not any(p.is_configured for p in providers.values()):
        return None

    _router = LLMRouter(providers, order=_order_from_settings(settings.llm_primary, list(providers.keys())))
    return _router


def _order_from_settings(primary: str, names: list[str]) -> list[str]:
    if primary in names:
        names = [primary] + [n for n in names if n != primary]
    return names


def reset_router_for_testing(router: LLMRouter | None) -> None:
    global _router
    _router = router
