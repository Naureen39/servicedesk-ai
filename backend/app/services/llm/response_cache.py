"""Semantic response cache (Section 4.5, item 4): before any RAG call, search response_cache
for a prior question with cosine similarity >= 0.92 and the same intent; return the cached
answer (zero LLM tokens) on a hit. TTL 30 days; invalidated whenever the source KB document
changes (dataset/scripts/embed_kb.py clears this table after re-embedding a changed document,
since a stale cached answer could reference outdated pricing, hours, or policy text).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assistant import ResponseCache
from app.services import settings_store
from app.services.embeddings import embed_query

TTL_DAYS = 30


async def lookup(db: AsyncSession, question: str, intent: str) -> str | None:
    query_vector = embed_query(question)
    distance = ResponseCache.question_embedding.cosine_distance(query_vector).label("distance")
    stmt = (
        select(ResponseCache, distance)
        .where(ResponseCache.intent == intent, ResponseCache.expires_at > datetime.now(UTC))
        .order_by(distance)
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        return None

    cached, dist = row
    similarity = 1.0 - float(dist)
    if similarity < settings_store.cache_similarity_threshold():
        return None

    await db.execute(update(ResponseCache).where(ResponseCache.id == cached.id).values(hits=cached.hits + 1))
    await db.commit()
    return cached.answer


async def store(db: AsyncSession, question: str, answer: str, intent: str) -> None:
    query_vector = embed_query(question)
    db.add(
        ResponseCache(
            question_embedding=query_vector,
            question=question,
            answer=answer,
            intent=intent,
            hits=0,
            expires_at=datetime.now(UTC) + timedelta(days=TTL_DAYS),
        )
    )
    await db.commit()
