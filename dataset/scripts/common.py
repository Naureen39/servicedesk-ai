"""Shared paths, logging, and small utilities for the dataset pipeline."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
DATASET_DIR = SCRIPTS_DIR.parent
REPO_ROOT = DATASET_DIR.parent

RAW_DIR = DATASET_DIR / "raw"
REFERENCE_DIR = DATASET_DIR / "reference"
PROCESSED_DIR = DATASET_DIR / "processed"
SYNTHETIC_DIR = DATASET_DIR / "synthetic"
DATA_CARD_PATH = DATASET_DIR / "DATA_CARD.md"
CHECKSUMS_PATH = DATASET_DIR / "checksums.sha256"

SEED = 20260924


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def ensure_dirs(*paths: Path) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)
