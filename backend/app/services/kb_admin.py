"""Knowledge Base admin (Section 8.3): "list, Markdown editor with preview, publish triggers
re-embedding." Real markdown files on disk stay the source of truth (the same
`dataset/reference/knowledge_base/*.md` files `dataset/scripts/embed_kb.py` reads), so editing
through the portal and editing the file directly are the same operation; publishing re-chunks
and re-embeds only the one changed document, using the same content-hash-diff approach as the
bulk pipeline, and invalidates the response cache for the same reason that script does (a
cached answer may now quote stale text).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.knowledge import KbChunk, KbDocument
from app.services.embeddings import embed_passages

REPO_ROOT = Path(__file__).resolve().parents[3]
CHUNK_MIN_WORDS = 220
CHUNK_MAX_WORDS = 380
OVERLAP_WORDS = 38


class KbDocumentNotFoundError(Exception):
    pass


def _resolve_path(source_path: str) -> Path:
    """`source_path` is always repo-root-relative (as stored in `kb_documents.source_path`);
    reject anything that would escape the knowledge_base directory."""
    resolved = (REPO_ROOT / source_path).resolve()
    kb_dir = (REPO_ROOT / "dataset" / "reference" / "knowledge_base").resolve()
    if kb_dir not in resolved.parents and resolved != kb_dir:
        raise ValueError("source_path must be under dataset/reference/knowledge_base/")
    return resolved


def read_document(source_path: str) -> str:
    path = _resolve_path(source_path)
    if not path.exists():
        raise KbDocumentNotFoundError(source_path)
    return path.read_text(encoding="utf-8")


def write_document(source_path: str, content: str) -> None:
    path = _resolve_path(source_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _split_by_heading(text_: str) -> list[tuple[str, str]]:
    lines = text_.splitlines()
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


def _chunk_words(words: list[str]) -> list[list[str]]:
    if len(words) <= CHUNK_MAX_WORDS:
        return [words]
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_MAX_WORDS, len(words))
        chunks.append(words[start:end])
        if end == len(words):
            break
        start = end - OVERLAP_WORDS
    return chunks


async def republish_document(db: AsyncSession, source_path: str, title: str | None = None) -> dict:
    """Re-chunks and re-embeds exactly one document. Returns
    {"chunk_count": int, "unchanged": bool}."""

    content = read_document(source_path)
    doc_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    existing = await db.execute(select(KbDocument).where(KbDocument.source_path == source_path))
    doc_row = existing.scalar_one_or_none()
    if doc_row is not None and doc_row.document_hash == doc_hash:
        return {"chunk_count": 0, "unchanged": True}

    resolved_title = title or Path(source_path).stem.replace("-", " ").title()

    chunk_rows: list[dict] = []
    for heading, section_text in _split_by_heading(content):
        words = section_text.split()
        for chunk in _chunk_words(words):
            chunk_content = " ".join(chunk)
            chunk_rows.append(
                {
                    "title": resolved_title,
                    "section": heading,
                    "content": chunk_content,
                    "content_hash": hashlib.sha256(chunk_content.encode("utf-8")).hexdigest(),
                }
            )

    embeddings = await asyncio.to_thread(embed_passages, [r["content"] for r in chunk_rows])

    await db.execute(delete(KbChunk).where(KbChunk.source_path == source_path))
    for row, vector in zip(chunk_rows, embeddings, strict=True):
        db.add(
            KbChunk(
                source_path=source_path, title=row["title"], section=row["section"],
                content=row["content"], content_hash=row["content_hash"], embedding=vector,
            )
        )

    if doc_row is None:
        db.add(KbDocument(source_path=source_path, title=resolved_title, document_hash=doc_hash))
    else:
        doc_row.title = resolved_title
        doc_row.document_hash = doc_hash

    # Same reasoning as the bulk pipeline (embed_kb.py): a cached answer may quote text this
    # publish just changed, and the KB is small enough that a full invalidation is cheap.
    await db.execute(text("TRUNCATE TABLE response_cache"))
    await db.commit()

    return {"chunk_count": len(chunk_rows), "unchanged": False}
