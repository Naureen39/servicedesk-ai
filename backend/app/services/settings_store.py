"""Runtime-editable settings (Section 8.3 Admin): the single `app_settings` row is the source
of truth, cached in-process (like `nlu/catalog_cache.py`) so the dialog manager and response
cache don't hit the DB on every turn -- refreshed immediately whenever an admin PATCHes it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import AppSettings

DEFAULTS = {
    "llm_primary": "groq",
    "confidence_threshold": 0.55,
    "cache_similarity_threshold": 0.92,
    "daily_budget_groq": 900,
    "daily_budget_gemini": 1400,
}


@dataclass
class _Cached:
    llm_primary: str = DEFAULTS["llm_primary"]
    confidence_threshold: float = DEFAULTS["confidence_threshold"]
    cache_similarity_threshold: float = DEFAULTS["cache_similarity_threshold"]
    daily_budget_groq: int = DEFAULTS["daily_budget_groq"]
    daily_budget_gemini: int = DEFAULTS["daily_budget_gemini"]


_cache = _Cached()


async def refresh(db: AsyncSession) -> None:
    global _cache
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        _cache = _Cached()
        return
    _cache = _Cached(
        llm_primary=row.llm_primary,
        confidence_threshold=float(row.confidence_threshold),
        cache_similarity_threshold=float(row.cache_similarity_threshold),
        daily_budget_groq=row.daily_budget_groq,
        daily_budget_gemini=row.daily_budget_gemini,
    )


def confidence_threshold() -> float:
    return _cache.confidence_threshold


def cache_similarity_threshold() -> float:
    return _cache.cache_similarity_threshold


def llm_primary() -> str:
    return _cache.llm_primary


def daily_budget_groq() -> int:
    return _cache.daily_budget_groq


def daily_budget_gemini() -> int:
    return _cache.daily_budget_gemini
