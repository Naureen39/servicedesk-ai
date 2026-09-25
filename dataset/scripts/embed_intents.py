"""Phase 3, item 3: embed all intent_examples into pgvector.

Combines the train/val/test intent splits built by build_intents.py (Phase 1) into one
deduplicated reference set and embeds each utterance (no query instruction prefix -- these are
the *candidates* a user's query is compared against, not queries themselves). Phase 4 uses this
table for nearest-neighbor intent fallback when the trained classifier's confidence is low, and
for the semantic response cache's intent tagging.

Requires DATABASE_URL and the sentence-transformers model; skips gracefully if either is
unavailable, matching embed_kb.py's behavior.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from common import PROCESSED_DIR, get_logger

logger = get_logger("embed_intents")

EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
SPLITS = ["intent_train.parquet", "intent_val.parquet", "intent_test.parquet"]


def load_combined_examples() -> pd.DataFrame:
    frames = []
    for name in SPLITS:
        path = PROCESSED_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"{path} not found; run build_intents.py first")
        frames.append(pd.read_parquet(path))
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["intent", "utterance"]).reset_index(drop=True)
    logger.info("Loaded %d unique (intent, utterance) examples across %d intents", len(combined), combined["intent"].nunique())
    return combined


def main() -> int:
    df = load_combined_examples()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping pgvector sync (Phase 2 dependency)")
        return 0

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.warning("sentence-transformers not installed (Phase 3 dependency); skipping pgvector sync")
        return 0

    import psycopg
    from pgvector.psycopg import register_vector

    with psycopg.connect(database_url) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'intent_examples')")
            if not cur.fetchone()[0]:
                logger.warning("intent_examples table not found (run Phase 2 Alembic migrations first)")
                return 0

        logger.info("Loading embedding model %s", EMBEDDING_MODEL_NAME)
        model = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu")
        embeddings = model.encode(df["utterance"].tolist(), normalize_embeddings=True, show_progress_bar=False)

        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE intent_examples RESTART IDENTITY")
            for (intent, utterance), embedding in zip(df[["intent", "utterance"]].itertuples(index=False), embeddings, strict=True):
                cur.execute(
                    "INSERT INTO intent_examples (intent, utterance, embedding) VALUES (%s, %s, %s)",
                    (intent, utterance, embedding.tolist()),
                )
        conn.commit()

    logger.info("Embedded and loaded %d intent examples into pgvector", len(df))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
