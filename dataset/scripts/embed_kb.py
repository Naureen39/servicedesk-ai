"""Phase 3: chunk the knowledge base and embed it into pgvector.

Splits each Markdown file in dataset/reference/knowledge_base/ by heading, then into 300-500
token chunks with 50 token overlap (approximated with a word-count heuristic, since the exact
tokenizer belongs to the embedding model). Stores title, section, source path, content, and a
content hash per chunk.

Re-embeds only changed documents (Section "Knowledge base admin page triggers re-embedding of
changed documents only (content hash)"): each source file's whole-document hash is compared
against `kb_documents.document_hash`; unchanged documents are left alone (their existing
`kb_chunks` rows and embeddings are reused untouched), and only changed or new documents have
their old chunks deleted and replaced.

Requires DATABASE_URL and the sentence-transformers model. When either is unavailable (for
example on a clean Phase-1-only clone), it still performs chunking and writes the result to
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


def load_embedder():
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model %s", EMBEDDING_MODEL_NAME)
    return SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu")


def embed_passages(model, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def get_existing_document_hashes(conn) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT source_path, document_hash FROM kb_documents")
        return dict(cur.fetchall())


def sync_to_pgvector(df: pd.DataFrame, database_url: str) -> tuple[int, int]:
    """Diffs by whole-document hash, re-embeds only changed/new documents.

    Returns (documents_reembedded, documents_unchanged).
    """
    import psycopg
    from pgvector.psycopg import register_vector

    with psycopg.connect(database_url) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'kb_chunks')")
            if not cur.fetchone()[0]:
                logger.warning("kb_chunks table not found (run Phase 2 Alembic migrations first)")
                return 0, 0

        existing_hashes = get_existing_document_hashes(conn)

        doc_hash_by_path = df.drop_duplicates("source_path").set_index("source_path")["document_hash"].to_dict()
        changed_paths = [
            path for path, doc_hash in doc_hash_by_path.items() if existing_hashes.get(path) != doc_hash
        ]
        unchanged_count = len(doc_hash_by_path) - len(changed_paths)

        if not changed_paths:
            logger.info("All %d documents unchanged (content hash match); nothing to re-embed", len(doc_hash_by_path))
            return 0, unchanged_count

        logger.info(
            "%d document(s) changed or new, %d unchanged: %s",
            len(changed_paths), unchanged_count, changed_paths,
        )

        changed_df = df[df["source_path"].isin(changed_paths)].reset_index(drop=True)
        model = load_embedder()
        embeddings = embed_passages(model, changed_df["content"].tolist())
        changed_df = changed_df.copy()
        changed_df["embedding"] = embeddings

        with conn.cursor() as cur:
            for path in changed_paths:
                cur.execute("DELETE FROM kb_chunks WHERE source_path = %s", (path,))

            for row in changed_df.itertuples():
                cur.execute(
                    """
                    INSERT INTO kb_chunks (source_path, title, section, content, content_hash, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (content_hash) DO NOTHING
                    """,
                    (row.source_path, row.title, row.section, row.content, row.content_hash, row.embedding),
                )

            for path in changed_paths:
                title = changed_df.loc[changed_df["source_path"] == path, "title"].iloc[0]
                cur.execute(
                    """
                    INSERT INTO kb_documents (source_path, title, document_hash, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (source_path) DO UPDATE
                        SET title = EXCLUDED.title,
                            document_hash = EXCLUDED.document_hash,
                            updated_at = now()
                    """,
                    (path, title, doc_hash_by_path[path]),
                )

            # Section 4.5, item 4: the semantic response cache is invalidated whenever the
            # source KB document changes, since a cached answer may quote now-outdated
            # pricing, hours, or policy text. The KB is small enough that clearing the whole
            # cache on any change is simpler than tracking which cached answers cited which
            # chunk, and costs nothing since cache entries are free to regenerate.
            cur.execute("TRUNCATE TABLE response_cache")
        conn.commit()

    logger.info("Re-embedded %d document(s), %d unchanged; response_cache invalidated", len(changed_paths), unchanged_count)
    return len(changed_paths), unchanged_count


def main() -> int:
    ensure_dirs(PROCESSED_DIR)
    df = build_chunks()

    preview_cols = ["source_path", "title", "section", "content", "word_count", "content_hash"]
    df[preview_cols].to_parquet(PROCESSED_DIR / "kb_chunks_preview.parquet", index=False)
    logger.info("Wrote chunk preview to %s", PROCESSED_DIR / "kb_chunks_preview.parquet")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping pgvector sync (Phase 2 dependency)")
        return 0

    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        logger.warning("sentence-transformers not installed (Phase 3 dependency); skipping pgvector sync")
        return 0

    sync_to_pgvector(df, database_url)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
