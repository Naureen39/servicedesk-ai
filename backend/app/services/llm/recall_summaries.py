"""Recall summaries generated once per campaign, reused forever (Section 4.5, item 3): zero
tokens for every user after the first. Falls back to a deterministic truncation of the NHTSA
text when no LLM provider is available, so the recall_check flow never blocks on the LLM.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.knowledge import RecallSummary
from app.services.llm.base import Message
from app.services.llm.prompts_loader import RECALL_SUMMARY, load_prompt
from app.services.llm.router import AllProvidersUnavailableError, LLMRouter

MAX_TOKENS = 90


class RecallLike(Protocol):
    """Structural type covering both `RecallRecord` (live NHTSA service, Section 5.1) and the
    legacy `RecallCampaign` DB row -- this function only reads these five fields."""

    campaign_number: str
    component: str
    summary: str
    consequence: str
    remedy: str


def _fallback_summary(campaign: RecallLike) -> str:
    summary = (campaign.summary or "").strip()
    remedy = (campaign.remedy or "").strip()
    short = summary[:220] + ("..." if len(summary) > 220 else "")
    return f"{short} This is repaired free of charge. {remedy[:150]}".strip()


async def get_or_create_summary(
    db: AsyncSession, campaign: RecallLike, router: LLMRouter | None
) -> tuple[str, str]:
    """Returns (summary_text, provider) where provider is "cached", "template", or the LLM
    provider name that generated it."""
    existing = await db.execute(select(RecallSummary).where(RecallSummary.campaign_number == campaign.campaign_number))
    row = existing.scalar_one_or_none()
    if row is not None:
        return row.short_summary, "cached"

    if router is not None:
        try:
            context = (
                f"Component: {campaign.component}\n"
                f"Defect summary: {campaign.summary}\n"
                f"Consequence: {campaign.consequence}\n"
                f"Remedy: {campaign.remedy}"
            )
            messages = [
                Message(role="system", content=load_prompt(RECALL_SUMMARY)),
                Message(role="user", content=context),
            ]
            result = await router.generate(db, messages, max_tokens=MAX_TOKENS)
            db.add(
                RecallSummary(
                    campaign_number=campaign.campaign_number,
                    short_summary=result.text.strip(),
                    voice_summary=result.text.strip(),
                    provider=result.provider,
                )
            )
            await db.commit()
            return result.text.strip(), result.provider
        except AllProvidersUnavailableError:
            pass

    fallback = _fallback_summary(campaign)
    db.add(
        RecallSummary(
            campaign_number=campaign.campaign_number,
            short_summary=fallback,
            voice_summary=fallback,
            provider="template",
        )
    )
    await db.commit()
    return fallback, "template"
