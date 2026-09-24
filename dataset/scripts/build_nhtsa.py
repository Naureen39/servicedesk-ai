"""Phase 1.3: parse NHTSA flat files (D2 recalls, D3 complaints) into analytics-ready tables.

Field positions below are taken directly from the NHTSA data dictionaries shipped alongside
the flat files (`RCL.txt` and `CMPL.txt`, downloaded next to the zips). Both files are
TAB-delimited with no header row and dates in YYYYMMDD format. The complaints file is read in
chunks to keep memory bounded.

Outputs:
  dataset/processed/recalls_subset.parquet
  dataset/processed/complaints_monthly.parquet
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pandas as pd
from common import PROCESSED_DIR, RAW_DIR, ensure_dirs, get_logger

logger = get_logger("build_nhtsa")

RCL_ZIP = RAW_DIR / "nhtsa" / "FLAT_RCL_POST_2010.zip"
CMPL_ZIP = RAW_DIR / "nhtsa" / "FLAT_CMPL.zip"
CATALOG_PATH = PROCESSED_DIR / "vehicle_catalog.parquet"

MIN_YEAR = 2014
COMPLAINT_CHUNK_ROWS = 200_000

# 0-indexed column positions, derived from RCL.txt field numbers (field N -> index N-1).
RCL_COLUMNS = {
    0: "record_id",
    1: "campaign_number",
    2: "make",
    3: "model",
    4: "model_year",
    6: "component",
    12: "notify_date",
    15: "report_date",
    19: "summary",
    20: "consequence",
    21: "remedy",
}

# 0-indexed column positions, derived from CMPL.txt field numbers (field N -> index N-1).
CMPL_COLUMNS = {
    3: "make",
    4: "model",
    5: "model_year",
    6: "crash",
    8: "fire",
    9: "injured",
    10: "deaths",
    11: "component",
    16: "received_date",
}


def _open_member_stream(zip_path: Path):
    zf = zipfile.ZipFile(zip_path)
    members = [n for n in zf.namelist() if n.lower().endswith(".txt")]
    if not members:
        raise RuntimeError(f"No .txt member found in {zip_path}")
    return zf, members[0]


def load_catalog_makes() -> set[str]:
    if not CATALOG_PATH.exists():
        logger.warning("%s not found; not filtering NHTSA data to catalog makes", CATALOG_PATH)
        return set()
    catalog = pd.read_parquet(CATALOG_PATH, columns=["make"])
    return set(catalog["make"].str.upper().unique())


def _read_flat(zip_path: Path, column_map: dict[int, str], chunksize: int | None = None):
    zf, member = _open_member_stream(zip_path)
    max_col = max(column_map)
    usecols = list(range(max_col + 1))
    reader = pd.read_csv(
        zf.open(member),
        sep="\t",
        header=None,
        usecols=usecols,
        names=[column_map.get(i, f"_col{i}") for i in usecols],
        dtype=str,
        encoding="latin-1",
        on_bad_lines="skip",
        quoting=3,  # csv.QUOTE_NONE: NHTSA text fields may contain stray quote chars
        chunksize=chunksize,
        engine="python" if chunksize is None else "c",
    )
    return reader, zf


def to_iso_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format="%Y%m%d", errors="coerce")


def build_recalls_subset(catalog_makes: set[str]) -> pd.DataFrame:
    if not RCL_ZIP.exists():
        raise FileNotFoundError(f"{RCL_ZIP} not found; run download.py first")

    reader, zf = _read_flat(RCL_ZIP, RCL_COLUMNS, chunksize=None)
    df = reader
    zf.close()
    logger.info("Loaded %d raw recall rows", len(df))

    df["make"] = df["make"].str.strip().str.upper()
    df["model"] = df["model"].str.strip()
    df["model_year"] = pd.to_numeric(df["model_year"], errors="coerce")
    df = df.dropna(subset=["model_year", "campaign_number"])
    df["model_year"] = df["model_year"].astype(int)
    df = df[df["model_year"] >= MIN_YEAR]

    if catalog_makes:
        df = df[df["make"].isin(catalog_makes)]

    df["report_date"] = to_iso_date(df["report_date"])
    df["notify_date"] = to_iso_date(df["notify_date"])

    keep = [
        "campaign_number",
        "make",
        "model",
        "model_year",
        "component",
        "summary",
        "consequence",
        "remedy",
        "report_date",
    ]
    df = df[keep].drop_duplicates(subset=["campaign_number", "make", "model", "model_year"])
    return df.sort_values(["report_date"], ascending=False).reset_index(drop=True)


def build_complaints_monthly(catalog_makes: set[str]) -> pd.DataFrame:
    if not CMPL_ZIP.exists():
        raise FileNotFoundError(f"{CMPL_ZIP} not found; run download.py first")

    reader, zf = _read_flat(CMPL_ZIP, CMPL_COLUMNS, chunksize=COMPLAINT_CHUNK_ROWS)

    aggregated: list[pd.DataFrame] = []
    total_rows = 0
    for i, chunk in enumerate(reader):
        total_rows += len(chunk)
        chunk["make"] = chunk["make"].str.strip().str.upper()
        chunk["model"] = chunk["model"].str.strip()
        chunk["model_year"] = pd.to_numeric(chunk["model_year"], errors="coerce")
        chunk = chunk.dropna(subset=["model_year"])
        chunk["model_year"] = chunk["model_year"].astype(int)
        chunk = chunk[chunk["model_year"] >= MIN_YEAR]

        if catalog_makes:
            chunk = chunk[chunk["make"].isin(catalog_makes)]
        if chunk.empty:
            continue

        chunk["received_date"] = to_iso_date(chunk["received_date"])
        chunk = chunk.dropna(subset=["received_date"])
        chunk["month"] = chunk["received_date"].dt.to_period("M").dt.to_timestamp()

        chunk["crash"] = (chunk["crash"].fillna("N") == "Y").astype(int)
        chunk["fire"] = (chunk["fire"].fillna("N") == "Y").astype(int)
        chunk["injured"] = pd.to_numeric(chunk["injured"], errors="coerce").fillna(0).astype(int)

        grouped = (
            chunk.groupby(["make", "model", "model_year", "component", "month"])
            .agg(count=("component", "size"), crash=("crash", "sum"), fire=("fire", "sum"), injured=("injured", "sum"))
            .reset_index()
        )
        aggregated.append(grouped)
        logger.info("Processed complaint chunk %d (%d rows so far)", i + 1, total_rows)

    zf.close()

    if not aggregated:
        logger.warning("No complaint rows matched filters; returning empty frame")
        return pd.DataFrame(
            columns=["make", "model", "model_year", "component", "month", "count", "crash", "fire", "injured"]
        )

    combined = pd.concat(aggregated, ignore_index=True)
    monthly = (
        combined.groupby(["make", "model", "model_year", "component", "month"])
        .agg(count=("count", "sum"), crash=("crash", "sum"), fire=("fire", "sum"), injured=("injured", "sum"))
        .reset_index()
        .sort_values(["month"], ascending=False)
    )
    logger.info("Read %d total complaint rows, aggregated to %d monthly rows", total_rows, len(monthly))
    return monthly


def main() -> int:
    ensure_dirs(PROCESSED_DIR)
    catalog_makes = load_catalog_makes()

    recalls = build_recalls_subset(catalog_makes)
    recalls_path = PROCESSED_DIR / "recalls_subset.parquet"
    recalls.to_parquet(recalls_path, index=False)
    logger.info("Wrote %d rows to %s", len(recalls), recalls_path)

    complaints = build_complaints_monthly(catalog_makes)
    complaints_path = PROCESSED_DIR / "complaints_monthly.parquet"
    complaints.to_parquet(complaints_path, index=False)
    logger.info("Wrote %d rows to %s", len(complaints), complaints_path)

    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
