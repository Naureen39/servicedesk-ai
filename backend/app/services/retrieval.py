"""Retrieval over the knowledge base and intent examples (Phase 3, items 3-4).

Cosine top-k with the HNSW index created in the Phase 2 migration
(`ix_kb_chunks_embedding_hnsw`, `ix_intent_examples_embedding_hnsw`). Chunks below
`min_similarity` are dropped entirely, per the plan: "if nothing passes, respond with a
fallback and offer a human" (Phase 4 wires that fallback into the dialog manager; this module
just returns an empty list in that case). An optional hybrid re-rank blends the vector score
with PostgreSQL full-text `ts_rank` keyword overlap.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.knowledge import IntentExample, KbChunk
from app.services.embeddings import embed_query

DEFAULT_TOP_K = 3
MIN_SIMILARITY = 0.55
HYBRID_CANDIDATE_POOL = 10


@dataclass
class RetrievedChunk:
    id: int
    source_path: str
    title: str | None
    section: str | None
    content: str
    similarity: float


@dataclass
class NearestIntent:
    intent: str
    utterance: str
    similarity: float


async def retrieve_kb_chunks(
    db: AsyncSession,
    query: str,
    k: int = DEFAULT_TOP_K,
    min_similarity: float = MIN_SIMILARITY,
    hybrid: bool = False,
) -> list[RetrievedChunk]:
    query_vector = embed_query(query)
    pool_size = HYBRID_CANDIDATE_POOL if hybrid else k

    distance = KbChunk.embedding.cosine_distance(query_vector).label("distance")
    stmt = select(KbChunk, distance).order_by(distance).limit(pool_size)
    result = await db.execute(stmt)
    rows = result.all()

    candidates = [
        RetrievedChunk(
            id=chunk.id,
            source_path=chunk.source_path,
            title=chunk.title,
            section=chunk.section,
            content=chunk.content,
            similarity=1.0 - float(dist),
        )
        for chunk, dist in rows
    ]
    candidates = [c for c in candidates if c.similarity >= min_similarity]

    if hybrid and candidates:
        candidates = await _rerank_hybrid(db, query, candidates)

    return candidates[:k]


async def _rerank_hybrid(db: AsyncSession, query: str, candidates: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Blends vector similarity with PostgreSQL full-text `ts_rank` keyword overlap:
    0.7 * cosine_similarity + 0.3 * normalized ts_rank, re-sorted descending."""
    ids = [c.id for c in candidates]
    result = await db.execute(
        text(
            """
            SELECT id, ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) AS rank
            FROM kb_chunks
            WHERE id = ANY(:ids)
            """
        ),
        {"query": query, "ids": ids},
    )
    ranks = {row.id: float(row.rank) for row in result.all()}
    max_rank = max(ranks.values(), default=0.0) or 1.0

    def combined_score(c: RetrievedChunk) -> float:
        keyword_score = ranks.get(c.id, 0.0) / max_rank
        return 0.7 * c.similarity + 0.3 * keyword_score

    return sorted(candidates, key=combined_score, reverse=True)


async def nearest_intent_examples(db: AsyncSession, query: str, k: int = 1) -> list[NearestIntent]:
    query_vector = embed_query(query)
    distance = IntentExample.embedding.cosine_distance(query_vector).label("distance")
    stmt = select(IntentExample, distance).order_by(distance).limit(k)
    result = await db.execute(stmt)
    return [
        NearestIntent(intent=row.intent, utterance=row.utterance, similarity=1.0 - float(dist))
        for row, dist in result.all()
    ]
