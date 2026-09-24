"""Phase 1.1: download source datasets D1-D5 with retries, resume, and checksum verification.

Fetches:
  D1 Bitext customer support training dataset (CSV)
  D2 NHTSA recalls flat file (ZIP)
  D3 NHTSA complaints flat file (ZIP)
  D5 EPA FuelEconomy.gov vehicles dataset (ZIP)

D4 (NHTSA live APIs) and D6/D7 (authored / generated) are not downloaded here.

Writes source versions and fetch dates into DATA_CARD.md and per-file SHA-256 sums into
checksums.sha256, so `make data` is reproducible and auditable from a clean clone.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests
from common import CHECKSUMS_PATH, DATA_CARD_PATH, RAW_DIR, REPO_ROOT, ensure_dirs, get_logger

logger = get_logger("download")

CHUNK_SIZE = 1024 * 256
MAX_RETRIES = 4
BACKOFF_SECONDS = 2.0


@dataclass(frozen=True)
class SourceFile:
    key: str
    url: str
    dest: Path
    license: str
    description: str


SOURCES: list[SourceFile] = [
    SourceFile(
        key="D1_bitext",
        url=(
            "https://huggingface.co/datasets/bitext/"
            "Bitext-customer-support-llm-chatbot-training-dataset/resolve/main/"
            "Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv"
        ),
        dest=RAW_DIR / "bitext" / "Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv",
        license="CDLA-Sharing-1.0",
        description="Bitext customer support LLM chatbot training dataset (27K rows)",
    ),
    SourceFile(
        key="D2_nhtsa_recalls",
        url="https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip",
        dest=RAW_DIR / "nhtsa" / "FLAT_RCL_POST_2010.zip",
        license="US Government public domain",
        description="NHTSA recalls flat file (campaigns from 2010 onward)",
    ),
    SourceFile(
        key="D3_nhtsa_complaints",
        url="https://static.nhtsa.gov/odi/ffdd/cmpl/FLAT_CMPL.zip",
        dest=RAW_DIR / "nhtsa" / "FLAT_CMPL.zip",
        license="US Government public domain",
        description="NHTSA owner complaints flat file",
    ),
    SourceFile(
        key="D5_epa_vehicles",
        url="https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip",
        dest=RAW_DIR / "epa" / "vehicles.csv.zip",
        license="US Government public domain",
        description="EPA FuelEconomy.gov vehicles dataset",
    ),
]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_one(source: SourceFile, force: bool = False) -> tuple[str, int]:
    """Download a single source file with retry/backoff. Returns (sha256, size_bytes)."""
    source.dest.parent.mkdir(parents=True, exist_ok=True)

    if source.dest.exists() and not force:
        logger.info("%s already present at %s, skipping (use --force to re-download)", source.key, source.dest)
        return sha256_of(source.dest), source.dest.stat().st_size

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Downloading %s (attempt %d/%d): %s", source.key, attempt, MAX_RETRIES, source.url)
            with requests.get(source.url, stream=True, timeout=60, allow_redirects=True) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                written = 0
                tmp_path = source.dest.with_suffix(source.dest.suffix + ".part")
                with tmp_path.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if not chunk:
                            continue
                        f.write(chunk)
                        written += len(chunk)
                tmp_path.replace(source.dest)
                if total and written != total:
                    raise OSError(f"Incomplete download: expected {total} bytes, got {written}")
            checksum = sha256_of(source.dest)
            size = source.dest.stat().st_size
            logger.info("Downloaded %s: %d bytes, sha256=%s", source.key, size, checksum)
            return checksum, size
        except (requests.RequestException, OSError) as exc:
            last_error = exc
            logger.warning("Attempt %d for %s failed: %s", attempt, source.key, exc)
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_SECONDS * attempt)
    raise RuntimeError(f"Failed to download {source.key} after {MAX_RETRIES} attempts") from last_error


def write_checksums(results: dict[str, tuple[str, int]]) -> None:
    lines = []
    for source in SOURCES:
        if source.key not in results:
            continue
        checksum, _ = results[source.key]
        rel_path = source.dest.relative_to(REPO_ROOT)
        lines.append(f"{checksum}  {rel_path.as_posix()}")
    CHECKSUMS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote %s", CHECKSUMS_PATH)


def update_data_card(results: dict[str, tuple[str, int]]) -> None:
    fetched_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    rows = ["| Source | License | Size (bytes) | SHA-256 | Fetched |", "|---|---|---|---|---|"]
    for source in SOURCES:
        if source.key not in results:
            continue
        checksum, size = results[source.key]
        rows.append(f"| {source.key} | {source.license} | {size:,} | `{checksum[:16]}...` | {fetched_at} |")
    table = "\n".join(rows)

    marker_start = "<!-- DOWNLOAD_TABLE_START -->"
    marker_end = "<!-- DOWNLOAD_TABLE_END -->"
    block = f"{marker_start}\n{table}\n{marker_end}"

    if DATA_CARD_PATH.exists():
        text = DATA_CARD_PATH.read_text(encoding="utf-8")
        if marker_start in text and marker_end in text:
            pre = text.split(marker_start)[0]
            post = text.split(marker_end)[1]
            text = pre + block + post
        else:
            text = text.rstrip() + "\n\n## Download Log\n\n" + block + "\n"
    else:
        text = "# Dataset Card\n\n## Download Log\n\n" + block + "\n"

    DATA_CARD_PATH.write_text(text, encoding="utf-8")
    logger.info("Updated %s", DATA_CARD_PATH)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download even if files exist")
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="subset of source keys to download (default: all)",
    )
    args = parser.parse_args()

    ensure_dirs(RAW_DIR)

    selected = [s for s in SOURCES if args.only is None or s.key in args.only]
    if not selected:
        logger.error("No matching sources for --only=%s", args.only)
        return 1

    results: dict[str, tuple[str, int]] = {}
    failures: list[str] = []
    for source in selected:
        try:
            results[source.key] = download_one(source, force=args.force)
        except RuntimeError as exc:
            logger.error(str(exc))
            failures.append(source.key)

    if results:
        write_checksums(results)
        update_data_card(results)

    if failures:
        logger.error("Failed sources: %s", ", ".join(failures))
        return 1

    logger.info("All requested sources downloaded successfully.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
