"""BAAI/bge-small-en-v1.5 embedding singleton (Phase 3, item 1).

Loaded once (CPU, normalized embeddings) and reused for every query and every ingestion job.
Per the model card, bge-small-en-v1.5 is an asymmetric retrieval model: short queries get an
instruction prefix so they embed closer to the long passages that answer them; passages
(knowledge base chunks, intent example utterances) are embedded as-is with no prefix.
"""

from __future__ import annotations

import threading

from app.core.config import get_settings

EMBEDDING_DIM = 384
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

_settings = get_settings()
_model = None
_model_lock = threading.Lock()


def get_embedder():
    """Returns the process-wide SentenceTransformer singleton, loading it on first call."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # re-check inside the lock
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(_settings.embedding_model, device="cpu")
    return _model


def embed_query(text: str) -> list[float]:
    model = get_embedder()
    vector = model.encode(QUERY_INSTRUCTION + text, normalize_embeddings=True)
    return vector.tolist()


def embed_passages(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_embedder()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def is_loaded() -> bool:
    return _model is not None
