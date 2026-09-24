"""Phase 1.4: build the intent training set.

Combines:
  - D1 (Bitext) rows mapped onto the automotive taxonomy via `bitext_intent_map`
  - authored automotive seed utterances (dataset/reference/intents/automotive_seed_utterances.csv)
  - rule-based augmentation: slot-value substitution, casual phrasing, light typos, and
    voice-style disfluencies, so each automotive intent reaches the 40-80 utterance target
    called for in the project plan without any LLM calls at build time.

Output: stratified 80/10/10 train/val/test parquet files under dataset/processed/.
"""

from __future__ import annotations

import random
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from common import PROCESSED_DIR, RAW_DIR, REFERENCE_DIR, SEED, ensure_dirs, get_logger

logger = get_logger("build_intents")

random.seed(SEED)
np.random.seed(SEED)

TAXONOMY_PATH = REFERENCE_DIR / "intents" / "intent_taxonomy.yaml"
SEEDS_PATH = REFERENCE_DIR / "intents" / "automotive_seed_utterances.csv"
BITEXT_CSV = RAW_DIR / "bitext" / "Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv"

MIN_PER_INTENT = 40
MAX_PER_INTENT = 80
MAX_BITEXT_PER_INTENT = 150

SLOT_VALUES = {
    "year": ["2015", "2018", "2019", "2020", "2021", "2022", "2023"],
    "make": ["Toyota", "Honda", "Ford", "Chevrolet", "Nissan", "Hyundai", "Subaru", "Jeep"],
    "model": ["Camry", "Civic", "F-150", "Silverado", "Altima", "Elantra", "Outback", "Grand Cherokee",
              "CR-V", "RAV4", "Accord", "Equinox"],
    "vin": ["1HGCM82633A004352", "5YJ3E1EA7KF317000", "3FA6P0H70ER123456", "1FTFW1ET5DFC12345"],
    "service": ["an oil change", "a brake inspection", "a tire rotation", "a 60k service",
                "an AC recharge", "a diagnostic check", "a transmission service"],
    "date": ["tomorrow", "next Tuesday", "this Friday", "next week", "Saturday morning", "the 14th"],
    "name": ["Alex Morgan", "Jamie Chen", "Taylor Brooks", "Sam Patel", "Jordan Reyes"],
    "phone": ["614-555-0123", "614-555-0198", "614-555-0177"],
    "ref_code": ["MRD-104822", "MRD-119047", "MRD-102355"],
}

CASUAL_PREFIXES = ["", "", "", "hey, ", "so ", "uh, ", "quick question, ", "hi, "]
CASUAL_SUFFIXES = ["", "", "", " please", " thanks", "?", " if that's possible"]
DISFLUENCIES = ["", "", "", "uh, ", "um, ", "yeah so ", "like, "]

TYPO_SWAPS = [
    (re.compile(r"\bappointment\b"), "appointmnet"),
    (re.compile(r"\bvehicle\b"), "vehcile"),
    (re.compile(r"\brecall\b"), "reacll"),
    (re.compile(r"\bschedule\b"), "shedule"),
]


def load_taxonomy() -> dict:
    with TAXONOMY_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_bitext(bitext_map: dict[str, str]) -> pd.DataFrame:
    if not BITEXT_CSV.exists():
        logger.warning("%s not found; skipping Bitext rows (run download.py first)", BITEXT_CSV)
        return pd.DataFrame(columns=["intent", "utterance"])

    df = pd.read_csv(BITEXT_CSV)
    text_col = next(c for c in df.columns if c.lower() in ("instruction", "utterance", "text"))
    intent_col = next(c for c in df.columns if c.lower() == "intent")

    df = df[[intent_col, text_col]].rename(columns={intent_col: "bitext_intent", text_col: "utterance"})
    df["intent"] = df["bitext_intent"].map(bitext_map)
    df = df.dropna(subset=["intent", "utterance"])
    logger.info("Mapped %d Bitext rows onto %d automotive intents", len(df), df["intent"].nunique())
    return df[["intent", "utterance"]]


def fill_slots(template: str) -> str:
    def repl(match: re.Match) -> str:
        key = match.group(1)
        values = SLOT_VALUES.get(key)
        if not values:
            return match.group(0)
        return random.choice(values)

    return re.sub(r"\{(\w+)\}", repl, template)


def apply_casual_variation(text: str, rng: random.Random) -> str:
    text = rng.choice(CASUAL_PREFIXES) + text
    if rng.random() < 0.25:
        text = rng.choice(DISFLUENCIES) + text
    text = text + rng.choice(CASUAL_SUFFIXES)
    if rng.random() < 0.12:
        pattern, replacement = rng.choice(TYPO_SWAPS)
        text = pattern.sub(replacement, text)
    return text.strip()


def augment_intent(seeds: list[str], target_min: int, target_max: int, rng: random.Random) -> list[str]:
    filled = [fill_slots(s) for s in seeds]
    unique = list(dict.fromkeys(filled))

    target = max(target_min, min(target_max, len(unique) * 3))
    results = set(unique)
    attempts = 0
    while len(results) < target and attempts < target * 10:
        base = rng.choice(seeds)
        variant = apply_casual_variation(fill_slots(base), rng)
        results.add(variant)
        attempts += 1

    return list(results)[:target_max]


def build_automotive_set(taxonomy: dict) -> pd.DataFrame:
    seeds_df = pd.read_csv(SEEDS_PATH)
    rng = random.Random(SEED)

    rows = []
    for intent_cfg in taxonomy["intents"]:
        intent = intent_cfg["name"]
        seeds = seeds_df.loc[seeds_df["intent"] == intent, "utterance"].tolist()
        if not seeds:
            logger.warning("No authored seeds for intent=%s", intent)
            continue
        augmented = augment_intent(seeds, MIN_PER_INTENT, MAX_PER_INTENT, rng)
        for utterance in augmented:
            rows.append({"intent": intent, "utterance": utterance})

    df = pd.DataFrame(rows)
    logger.info("Built %d automotive-seeded utterances across %d intents", len(df), df["intent"].nunique())
    return df


def stratified_split(df: pd.DataFrame, train: float = 0.8, val: float = 0.1) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_parts, val_parts, test_parts = [], [], []
    rng = np.random.RandomState(SEED)
    for intent, group in df.groupby("intent"):
        group = group.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
        n = len(group)
        n_train = max(1, int(round(n * train)))
        n_val = max(1, int(round(n * val))) if n >= 3 else 0
        n_train = min(n_train, n - (1 if n - n_train < 1 else 0))
        train_parts.append(group.iloc[:n_train])
        val_parts.append(group.iloc[n_train:n_train + n_val])
        test_parts.append(group.iloc[n_train + n_val:])
    return (
        pd.concat(train_parts).sample(frac=1.0, random_state=SEED).reset_index(drop=True),
        pd.concat(val_parts).sample(frac=1.0, random_state=SEED).reset_index(drop=True),
        pd.concat(test_parts).sample(frac=1.0, random_state=SEED).reset_index(drop=True),
    )


def main() -> int:
    ensure_dirs(PROCESSED_DIR)
    taxonomy = load_taxonomy()

    automotive_df = build_automotive_set(taxonomy)
    bitext_df = load_bitext(taxonomy["bitext_intent_map"])

    combined = pd.concat([automotive_df, bitext_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["intent", "utterance"]).dropna()
    combined["utterance"] = combined["utterance"].astype(str).str.strip()
    combined = combined[combined["utterance"].str.len() > 0]

    logger.info("Combined dataset: %d rows across %d intents", len(combined), combined["intent"].nunique())
    logger.info("Per-intent counts:\n%s", combined["intent"].value_counts().to_string())

    train_df, val_df, test_df = stratified_split(combined)

    train_df.to_parquet(PROCESSED_DIR / "intent_train.parquet", index=False)
    val_df.to_parquet(PROCESSED_DIR / "intent_val.parquet", index=False)
    test_df.to_parquet(PROCESSED_DIR / "intent_test.parquet", index=False)

    logger.info(
        "Wrote splits: train=%d val=%d test=%d to %s",
        len(train_df), len(val_df), len(test_df), PROCESSED_DIR,
    )
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
