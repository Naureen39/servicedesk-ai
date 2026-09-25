"""Builds the process-wide LLMRouter from settings (Section 4.4: "Primary and fallback order
from settings")."""

from __future__ import annotations

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

    providers = {"groq": GroqProvider(), "gemini": GeminiProvider()}
    if not any(p.is_configured for p in providers.values()):
        return None

    # No explicit `order` here: LLMRouter.order reads the live, admin-editable setting
    # (Section 8.3) on every access, falling back to the env default (settings.llm_primary)
    # until the settings_store cache is first refreshed at startup.
    _router = LLMRouter(providers)
    return _router


def reset_router_for_testing(router: LLMRouter | None) -> None:
    global _router
    _router = router
