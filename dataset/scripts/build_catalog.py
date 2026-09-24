"""Phase 1.2: build the vehicle catalog from the EPA FuelEconomy.gov dataset (D5).

Keeps model years 2010+, restricts to the top 15 US makes by row count, normalizes make/model
names, and stores an `nhtsa_model_name` column derived from NHTSA vPIC's `GetModelsForMake`
endpoint so downstream NHTSA lookups (Phase 5) never pass raw EPA spelling to NHTSA.

Output: dataset/processed/vehicle_catalog.parquet
"""

from __future__ import annotations

import re
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests
from common import PROCESSED_DIR, RAW_DIR, ensure_dirs, get_logger

logger = get_logger("build_catalog")

EPA_ZIP = RAW_DIR / "epa" / "vehicles.csv.zip"
MIN_YEAR = 2010
TOP_N_MAKES = 15
VPIC_MODELS_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/{make}?format=json"

# EPA make spellings that need normalization before matching NHTSA naming.
MAKE_ALIASES = {
    "Chevrolet": "Chevrolet",
    "Mercedes-Benz": "Mercedes-Benz",
    "MINI": "MINI",
    "Ram": "RAM",
}


def load_epa_vehicles() -> pd.DataFrame:
    if not EPA_ZIP.exists():
        raise FileNotFoundError(f"{EPA_ZIP} not found; run download.py first")
    with zipfile.ZipFile(EPA_ZIP) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise RuntimeError(f"No CSV found inside {EPA_ZIP}")
        with zf.open(csv_names[0]) as f:
            df = pd.read_csv(f, low_memory=False)
    logger.info("Loaded %d raw EPA vehicle rows from %s", len(df), csv_names[0])
    return df


def normalize_make(make: str) -> str:
    make = str(make).strip()
    return MAKE_ALIASES.get(make, make)


def normalize_model(model: str) -> str:
    model = str(model).strip()
    model = re.sub(r"\s+", " ", model)
    return model


def fetch_nhtsa_models_for_make(make: str, session: requests.Session) -> set[str]:
    try:
        resp = session.get(VPIC_MODELS_URL.format(make=requests.utils.quote(make)), timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        return {row["Model_Name"] for row in payload.get("Results", []) if row.get("Model_Name")}
    except requests.RequestException as exc:
        logger.warning("vPIC lookup failed for make=%s: %s", make, exc)
        return set()


def best_nhtsa_match(model: str, nhtsa_models: set[str]) -> str:
    if not nhtsa_models:
        return model
    if model in nhtsa_models:
        return model
    lower_map = {m.lower(): m for m in nhtsa_models}
    if model.lower() in lower_map:
        return lower_map[model.lower()]
    try:
        from rapidfuzz import process

        match = process.extractOne(model, list(nhtsa_models))
        if match and match[1] >= 85:
            return match[0]
    except ImportError:
        pass
    return model


def build_catalog(sample_makes_for_nhtsa: bool = True) -> pd.DataFrame:
    df = load_epa_vehicles()

    cols = {c.lower(): c for c in df.columns}
    year_col = cols.get("year")
    make_col = cols.get("make")
    model_col = cols.get("model")
    if not all([year_col, make_col, model_col]):
        raise RuntimeError(f"Expected year/make/model columns in EPA data, got {list(df.columns)[:20]}")

    df = df[[year_col, make_col, model_col]].rename(
        columns={year_col: "year", make_col: "make", model_col: "model"}
    )
    df = df.dropna(subset=["year", "make", "model"])
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    df = df[df["year"] >= MIN_YEAR]

    df["make"] = df["make"].map(normalize_make)
    df["model"] = df["model"].map(normalize_model)

    top_makes = df["make"].value_counts().head(TOP_N_MAKES).index.tolist()
    logger.info("Top %d makes by row count: %s", TOP_N_MAKES, top_makes)
    df = df[df["make"].isin(top_makes)]

    catalog = df.drop_duplicates(subset=["year", "make", "model"]).sort_values(
        ["make", "model", "year"]
    ).reset_index(drop=True)

    catalog["nhtsa_model_name"] = catalog["model"]

    if sample_makes_for_nhtsa:
        session = requests.Session()
        make_model_map: dict[str, set[str]] = {}
        for make in top_makes:
            make_model_map[make] = fetch_nhtsa_models_for_make(make, session)
            time.sleep(0.2)

        def resolve(row: pd.Series) -> str:
            return best_nhtsa_match(row["model"], make_model_map.get(row["make"], set()))

        catalog["nhtsa_model_name"] = catalog.apply(resolve, axis=1)

    return catalog


def main() -> int:
    ensure_dirs(PROCESSED_DIR)
    skip_nhtsa = "--no-nhtsa-crosscheck" in sys.argv
    catalog = build_catalog(sample_makes_for_nhtsa=not skip_nhtsa)
    out_path = PROCESSED_DIR / "vehicle_catalog.parquet"
    catalog.to_parquet(out_path, index=False)
    logger.info("Wrote %d rows to %s", len(catalog), out_path)
    logger.info("Years: %d-%d, makes: %d", catalog["year"].min(), catalog["year"].max(), catalog["make"].nunique())
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
