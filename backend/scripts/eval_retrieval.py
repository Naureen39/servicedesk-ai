"""Phase 3 DoD: retrieval evaluation set of 60 questions reaches hit rate @3 >= 90%,
p95 query latency < 60 ms.

Runs each question in dataset/reference/eval/kb_retrieval_questions.csv through the same
retrieve_kb_chunks() service the backend uses, checks whether the expected source document
appears among the top-3 results, and times each call (embedding + pgvector search) to compute
p95 latency. Prints a report and writes it to docs/retrieval-evaluation.md; exits non-zero if
either target is missed, so this is a real gate, not just a report.
"""

from __future__ import annotations

import asyncio
import csv
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import async_session_factory
from app.services.embeddings import get_embedder
from app.services.retrieval import retrieve_kb_chunks

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_SET_PATH = REPO_ROOT / "dataset" / "reference" / "eval" / "kb_retrieval_questions.csv"
DOCS_OUT_PATH = REPO_ROOT / "docs" / "retrieval-evaluation.md"

HIT_RATE_TARGET = 0.90
P95_LATENCY_TARGET_MS = 60.0
TOP_K = 3


def load_questions() -> list[dict]:
    with EVAL_SET_PATH.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


async def run_eval() -> dict:
    questions = load_questions()
    print(f"Loaded {len(questions)} evaluation questions from {EVAL_SET_PATH}")

    # Warm the model up once outside the timed loop (matches the app's own startup behavior),
    # so the measured latencies reflect steady-state query cost, not one-time model load.
    get_embedder()

    latencies_ms: list[float] = []
    misses: list[tuple[str, str, list[str]]] = []
    hits = 0

    async with async_session_factory() as db:
        for row in questions:
            start = time.perf_counter()
            results = await retrieve_kb_chunks(db, row["question"], k=TOP_K)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies_ms.append(elapsed_ms)

            retrieved_docs = [Path(r.source_path).name for r in results]
            if row["expected_doc"] in retrieved_docs:
                hits += 1
            else:
                misses.append((row["question"], row["expected_doc"], retrieved_docs))

    hit_rate = hits / len(questions)
    latencies_sorted = sorted(latencies_ms)
    p95_index = min(len(latencies_sorted) - 1, round(0.95 * (len(latencies_sorted) - 1)))
    p95_ms = latencies_sorted[p95_index]

    return {
        "n": len(questions),
        "hits": hits,
        "hit_rate": hit_rate,
        "p50_ms": statistics.median(latencies_ms),
        "p95_ms": p95_ms,
        "max_ms": max(latencies_ms),
        "mean_ms": statistics.mean(latencies_ms),
        "misses": misses,
    }


def write_report(report: dict, passed: bool) -> None:
    DOCS_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Retrieval Evaluation (Phase 3)",
        "",
        f"Evaluation set: `{EVAL_SET_PATH.relative_to(REPO_ROOT).as_posix()}` ({report['n']} questions)",
        f"Model: `BAAI/bge-small-en-v1.5`, top-k={TOP_K}, min similarity 0.55",
        "",
        "## Results",
        "",
        f"- Hit rate @{TOP_K}: **{report['hit_rate']:.1%}** ({report['hits']}/{report['n']}), target >= {HIT_RATE_TARGET:.0%}",
        f"- p95 latency: **{report['p95_ms']:.1f} ms**, target < {P95_LATENCY_TARGET_MS:.0f} ms",
        f"- p50 latency: {report['p50_ms']:.1f} ms, mean: {report['mean_ms']:.1f} ms, max: {report['max_ms']:.1f} ms",
        f"- Overall: **{'PASSED' if passed else 'FAILED'}**",
        "",
    ]
    if report["misses"]:
        lines.append("## Misses")
        lines.append("")
        lines.append("| Question | Expected | Retrieved |")
        lines.append("|---|---|---|")
        for question, expected, retrieved in report["misses"]:
            lines.append(f"| {question} | {expected} | {', '.join(retrieved) or '(none passed min similarity)'} |")
        lines.append("")

    DOCS_OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote report to {DOCS_OUT_PATH}")


def main() -> int:
    report = asyncio.run(run_eval())

    hit_rate_ok = report["hit_rate"] >= HIT_RATE_TARGET
    latency_ok = report["p95_ms"] < P95_LATENCY_TARGET_MS
    passed = hit_rate_ok and latency_ok

    print(f"Hit rate @{TOP_K}: {report['hit_rate']:.1%} ({report['hits']}/{report['n']}) "
          f"{'OK' if hit_rate_ok else 'BELOW TARGET'} (target >= {HIT_RATE_TARGET:.0%})")
    print(f"p95 latency: {report['p95_ms']:.1f} ms {'OK' if latency_ok else 'ABOVE TARGET'} "
          f"(target < {P95_LATENCY_TARGET_MS:.0f} ms)")
    if report["misses"]:
        print(f"\n{len(report['misses'])} miss(es):")
        for question, expected, retrieved in report["misses"]:
            print(f"  - {question!r} expected={expected} got={retrieved}")

    write_report(report, passed)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
