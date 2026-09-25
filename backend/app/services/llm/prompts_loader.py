"""Loads versioned prompt template files (Section 4.6: "Store in services/llm/prompts/ as
versioned files"). Cached in memory since the files never change at runtime."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

GROUNDED_ANSWER = "grounded_answer.v1"
RECALL_SUMMARY = "recall_summary.v1"
CLARIFICATION_REPHRASE = "clarification_rephrase.v1"


@lru_cache(maxsize=16)
def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip()
