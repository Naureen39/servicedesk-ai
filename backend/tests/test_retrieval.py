"""Phase 3: embedding singleton + cosine top-k retrieval, against the real model and a real
pgvector-backed database (not mocked), since the whole point is validating that the HNSW
index and cosine distance operator actually return the right thing.
"""

from __future__ import annotations

import math

import pytest
from sqlalchemy import text

from app.db.base import async_session_factory
from app.services.embeddings import embed_passages, embed_query, get_embedder
from app.services.retrieval import nearest_intent_examples, retrieve_kb_chunks


def test_embed_query_returns_normalized_384_dim_vector():
    vector = embed_query("What are your hours on Saturday?")
    assert len(vector) == 384
    norm = math.sqrt(sum(v * v for v in vector))
    assert norm == pytest.approx(1.0, abs=1e-3)


def test_embedder_is_a_singleton():
    assert get_embedder() is get_embedder()


@pytest.fixture
async def seeded_kb_chunks():
    texts = [
        "Our service centers are open Monday through Saturday; we are closed on Sundays and major holidays.",
        "Oil changes should be done every 5,000 to 7,500 miles with conventional oil, or every 7,500 to 10,000 miles with synthetic oil.",
        "The quarterly financial report shows revenue grew twelve percent compared to last year.",
    ]
    embeddings = embed_passages(texts)
    async with async_session_factory() as db:
        for i, (content, embedding) in enumerate(zip(texts, embeddings, strict=True)):
            await db.execute(
                text(
                    """
                    INSERT INTO kb_chunks (source_path, title, section, content, content_hash, embedding)
                    VALUES (:path, :title, :section, :content, :hash, CAST(:embedding AS vector))
                    """
                ),
                {
                    "path": f"dataset/reference/knowledge_base/test-doc-{i}.md",
                    "title": f"Test Doc {i}",
                    "section": "Test Section",
                    "content": content,
                    "hash": f"test-hash-{i}",
                    "embedding": str(embedding),
                },
            )
        await db.commit()
    yield texts
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM kb_chunks WHERE content_hash LIKE 'test-hash-%'"))
        await db.commit()


@pytest.mark.asyncio
async def test_retrieve_kb_chunks_finds_relevant_chunk_above_threshold(seeded_kb_chunks):
    async with async_session_factory() as db:
        # k=5, not 3: the real knowledge base is also loaded into this test database (by the
        # dialog-manager fixtures), so the genuine "Hours And Locations" doc is a legitimate,
        # even stronger match for this query than the synthetic seeded chunk -- this test only
        # needs to confirm the seeded chunk clears the similarity bar and is retrievable, not
        # that it outranks real production content.
        results = await retrieve_kb_chunks(db, "What time do you open on Saturdays?", k=5)
    assert len(results) >= 1
    test_doc_hits = [r for r in results if r.title == "Test Doc 0"]
    assert test_doc_hits, f"expected 'Test Doc 0' among the top results, got {[r.title for r in results]}"
    assert test_doc_hits[0].similarity >= 0.55


@pytest.mark.asyncio
async def test_retrieve_kb_chunks_excludes_unrelated_chunk(seeded_kb_chunks):
    async with async_session_factory() as db:
        results = await retrieve_kb_chunks(db, "What time do you open on Saturdays?", k=3)
    titles = [r.title for r in results]
    assert "Test Doc 2" not in titles  # the financial-report sentence is not about hours


@pytest.mark.asyncio
async def test_retrieve_kb_chunks_returns_empty_when_nothing_passes_threshold(seeded_kb_chunks):
    async with async_session_factory() as db:
        results = await retrieve_kb_chunks(db, "quarterly earnings and stock buybacks", k=3, min_similarity=0.99)
    assert results == []


@pytest.mark.asyncio
async def test_retrieve_kb_chunks_hybrid_rerank_still_returns_relevant_chunk(seeded_kb_chunks):
    async with async_session_factory() as db:
        results = await retrieve_kb_chunks(db, "oil change interval synthetic", k=3, hybrid=True)
    assert any(r.title == "Test Doc 1" for r in results)


@pytest.fixture
async def seeded_intent_examples():
    examples = [("recall_check", "is there a recall on my car"), ("book_service", "I need to book an oil change")]
    embeddings = embed_passages([u for _, u in examples])
    async with async_session_factory() as db:
        for (intent, utterance), embedding in zip(examples, embeddings, strict=True):
            await db.execute(
                text(
                    "INSERT INTO intent_examples (intent, utterance, embedding) "
                    "VALUES (:intent, :utterance, CAST(:embedding AS vector))"
                ),
                {"intent": intent, "utterance": utterance, "embedding": str(embedding)},
            )
        await db.commit()
    yield
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM intent_examples WHERE intent IN ('recall_check', 'book_service')"))
        await db.commit()


@pytest.mark.asyncio
async def test_nearest_intent_examples_finds_closest_match(seeded_intent_examples):
    async with async_session_factory() as db:
        results = await nearest_intent_examples(db, "does my vehicle have any open recalls", k=1)
    assert len(results) == 1
    assert results[0].intent == "recall_check"
