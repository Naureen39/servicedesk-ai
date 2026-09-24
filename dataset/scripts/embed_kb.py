"""Phase 1 support / Phase 3 dependency: chunk the knowledge base and embed it into pgvector.

Splits each Markdown file in dataset/reference/knowledge_base/ by heading, then into 300-500
token chunks with 50 token overlap (approximated with a word-count heuristic since the exact
tokenizer belongs to the embedding model loaded in Phase 3). Stores title, section, source
path, content, and a content hash so re-embedding only touches changed documents (Section 3.5).

This script requires the `kb_chunks` table from the Phase 2 Alembic migrations and the
sentence-transformers embedding model from Phase 3. When either is unavailable (for example
on a clean Phase-1-only clone), it still performs chunking and writes the result to
dataset/processed/kb_chunks_preview.parquet so the chunking logic can be verified end to end
without a live database or a downloaded model.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

import pandas as pd
from common import PROCESSED_DIR, REFERENCE_DIR, ensure_dirs, get_logger

logger = get_logger("embed_kb")

KB_DIR = REFERENCE_DIR / "knowledge_base"
CHUNK_MIN_WORDS = 220  # approximates 300 tokens
CHUNK_MAX_WORDS = 380  # approximates 500 tokens
OVERLAP_WORDS = 38  # approximates 50 tokens
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")


def split_by_heading(text: str) -> list[tuple[str, str]]:
    """Returns list of (heading, section_text) using Markdown '#'/'##' headings."""
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_heading = "Introduction"
    current_lines: list[str] = []
    for line in lines:
        if re.match(r"^#{1,3}\s+", line):
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = re.sub(r"^#{1,3}\s+", "", line).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, current_lines))
    return [(h, "\n".join(lines).strip()) for h, lines in sections if "\n".join(lines).strip()]


def chunk_words(words: list[str], min_words: int, max_words: int, overlap: int) -> list[list[str]]:
    if len(words) <= max_words:
        return [words]
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(words[start:end])
        if end == len(words):
            break
        start = end - overlap
    return chunks


def build_chunks() -> pd.DataFrame:
    rows = []
    md_files = sorted(KB_DIR.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"No knowledge base documents found in {KB_DIR}")

    for path in md_files:
        text = path.read_text(encoding="utf-8")
        title = path.stem.replace("-", " ").title()
        doc_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        for heading, section_text in split_by_heading(text):
            words = section_text.split()
            for chunk in chunk_words(words, CHUNK_MIN_WORDS, CHUNK_MAX_WORDS, OVERLAP_WORDS):
                content = " ".join(chunk)
                chunk_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                rows.append(
                    {
                        "source_path": str(path.relative_to(REFERENCE_DIR.parent.parent)),
                        "title": title,
                        "section": heading,
                        "content": content,
                        "word_count": len(chunk),
                        "content_hash": chunk_hash,
                        "document_hash": doc_hash,
                    }
                )

    df = pd.DataFrame(rows)
    logger.info("Built %d chunks from %d knowledge base documents", len(df), len(md_files))
    return df


def try_embed(df: pd.DataFrame) -> pd.DataFrame | None:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.warning(
            "sentence-transformers not installed (Phase 3 dependency); skipping embedding, "
            "chunk preview only."
        )
        return None

    logger.info("Loading embedding model %s", EMBEDDING_MODEL_NAME)
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    embeddings = model.encode(df["content"].tolist(), normalize_embeddings=True, show_progress_bar=True)
    df = df.copy()
    df["embedding"] = list(embeddings)
    return df


def try_upsert_pgvector(df: pd.DataFrame) -> bool:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping pgvector upsert (Phase 2 dependency)")
        return False
    if "embedding" not in df.columns:
        logger.warning("No embeddings computed; skipping pgvector upsert")
        return False

    try:
        import psycopg
    except ImportError:
        logger.warning("psycopg not installed; skipping pgvector upsert")
        return False

    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables WHERE table_name = 'kb_chunks'
                    )
                    """
                )
                exists = cur.fetchone()[0]
                if not exists:
                    logger.warning("kb_chunks table not found (run Phase 2 Alembic migrations first)")
                    return False
                for row in df.itertuples():
                    cur.execute(
                        """
                        INSERT INTO kb_chunks (source_path, title, section, content, content_hash, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (content_hash) DO NOTHING
                        """,
                        (row.source_path, row.title, row.section, row.content, row.content_hash, list(row.embedding)),
                    )
            conn.commit()
        logger.info("Upserted %d chunks into kb_chunks", len(df))
        return True
    except Exception as exc:  # pragma: no cover - depends on live Phase 2 DB
        logger.error("pgvector upsert failed: %s", exc)
        return False


def main() -> int:
    ensure_dirs(PROCESSED_DIR)
    df = build_chunks()

    preview_cols = ["source_path", "title", "section", "content", "word_count", "content_hash"]
    df[preview_cols].to_parquet(PROCESSED_DIR / "kb_chunks_preview.parquet", index=False)
    logger.info("Wrote chunk preview to %s", PROCESSED_DIR / "kb_chunks_preview.parquet")

    embedded = try_embed(df)
    if embedded is not None:
        try_upsert_pgvector(embedded)

    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
