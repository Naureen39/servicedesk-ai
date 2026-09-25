"""Resolves a user's typed make/model to the exact spelling NHTSA's APIs expect (Section 5.1:
"Resolve user vehicle to NHTSA names through products endpoints ... plus rapidfuzz; if
ambiguous ... ask a single disambiguation question with options"). Never passes raw user text
straight into recallsByVehicle/complaintsByVehicle, since NHTSA's make/model spelling is exact
match only (e.g. "F150" vs "F-150" vs "F 150" all fail silently as zero results).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.nhtsa.client import get_json

PRODUCTS_MAKES_URL = "https://api.nhtsa.gov/products/vehicle/makes"
PRODUCTS_MODELS_URL = "https://api.nhtsa.gov/products/vehicle/models"

EXACT_MATCH_SCORE = 100.0
DISAMBIGUATION_SCORE_FLOOR = 70.0


@dataclass
class ResolvedVehicle:
    make: str
    model: str


@dataclass
class Ambiguous:
    candidates: list[str]


async def resolve_make(year: int, make: str) -> str | None:
    data = await get_json(PRODUCTS_MAKES_URL, {"modelYear": year, "issueType": "r"})
    makes = {row["make"] for row in data.get("results", [])}
    if not makes:
        return None

    from rapidfuzz import fuzz, process

    match = process.extractOne(make.upper(), list(makes), scorer=fuzz.ratio)
    if match and match[1] >= DISAMBIGUATION_SCORE_FLOOR:
        return match[0]
    return None


async def resolve_model(year: int, make: str, model: str) -> ResolvedVehicle | Ambiguous | None:
    data = await get_json(PRODUCTS_MODELS_URL, {"modelYear": year, "make": make, "issueType": "r"})
    models = sorted({row["model"] for row in data.get("results", [])})
    if not models:
        return None

    from rapidfuzz import fuzz, process

    matches = process.extract(model.upper(), models, scorer=fuzz.WRatio, limit=5)
    if not matches:
        return None

    best_score = matches[0][1]
    if best_score >= 95:
        return ResolvedVehicle(make=make, model=matches[0][0])

    close_candidates = [m for m, score, _ in matches if score >= DISAMBIGUATION_SCORE_FLOOR and score >= best_score - 10]
    if len(close_candidates) > 1:
        # e.g. "F-150" resolving to both "F-150" and "F-150 HEAVY DUTY" (Section 5.1 example).
        return Ambiguous(candidates=close_candidates)
    if close_candidates:
        return ResolvedVehicle(make=make, model=close_candidates[0])
    return None
