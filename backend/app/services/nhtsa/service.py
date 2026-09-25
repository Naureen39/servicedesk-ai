"""High-level NHTSA service (Section 5.1): live recalls/complaints/VIN decode, each cached in
`nhtsa_cache` for 24 hours so a popular vehicle doesn't cost a fresh API call on every ask.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.knowledge import NhtsaCache
from app.services.nhtsa.client import NHTSAClientError, get_json
from app.services.nhtsa.resolver import Ambiguous, ResolvedVehicle, resolve_make, resolve_model

RECALLS_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"
COMPLAINTS_URL = "https://api.nhtsa.gov/complaints/complaintsByVehicle"
VPIC_DECODE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"

CACHE_TTL_HOURS = 24


@dataclass
class RecallRecord:
    campaign_number: str
    component: str
    summary: str
    consequence: str
    remedy: str
    report_date: str  # ISO 8601


@dataclass
class ComplaintComponentSummary:
    component: str
    count: int
    crash_count: int
    fire_count: int


def _normalize_recall_date(raw: str | None) -> str | None:
    """Section 4 note: "recall API dates use DD/MM/YYYY while complaint API dates use
    MM/DD/YYYY". Returns ISO 8601 (YYYY-MM-DD), or None if unparseable."""
    if not raw:
        return None
    try:
        day, month, year = raw.split("/")
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except ValueError:
        return None


def _normalize_complaint_date(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        month, day, year = raw.split("/")
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except ValueError:
        return None


async def _cache_get(db: AsyncSession, key: str) -> dict | None:
    result = await db.execute(select(NhtsaCache).where(NhtsaCache.request_key == key))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    if row.fetched_at < datetime.now(UTC) - timedelta(hours=CACHE_TTL_HOURS):
        return None
    return row.payload


async def _cache_put(db: AsyncSession, key: str, payload: dict) -> None:
    existing = await db.execute(select(NhtsaCache).where(NhtsaCache.request_key == key))
    row = existing.scalar_one_or_none()
    if row is None:
        db.add(NhtsaCache(request_key=key, payload=payload, fetched_at=datetime.now(UTC)))
    else:
        row.payload = payload
        row.fetched_at = datetime.now(UTC)
    await db.commit()


async def resolve_vehicle(db: AsyncSession, year: int, make: str, model: str) -> ResolvedVehicle | Ambiguous | None:
    resolved_make = await resolve_make(year, make)
    if resolved_make is None:
        return None
    return await resolve_model(year, resolved_make, model)


async def get_recalls(db: AsyncSession, year: int, make: str, model: str) -> list[RecallRecord]:
    cache_key = f"recalls:{year}:{make.upper()}:{model.upper()}"
    cached = await _cache_get(db, cache_key)
    if cached is not None:
        payload = cached
    else:
        try:
            payload = await get_json(RECALLS_URL, {"make": make, "model": model, "modelYear": year})
        except NHTSAClientError:
            return []
        await _cache_put(db, cache_key, payload)

    records = []
    for row in payload.get("results", []):
        records.append(
            RecallRecord(
                campaign_number=row.get("NHTSACampaignNumber", ""),
                component=row.get("Component", ""),
                summary=row.get("Summary", ""),
                consequence=row.get("Consequence", ""),
                remedy=row.get("Remedy", ""),
                report_date=_normalize_recall_date(row.get("ReportReceivedDate")) or "",
            )
        )
    records.sort(key=lambda r: r.report_date, reverse=True)
    return records


async def get_complaints_summary(db: AsyncSession, year: int, make: str, model: str) -> list[ComplaintComponentSummary]:
    cache_key = f"complaints:{year}:{make.upper()}:{model.upper()}"
    cached = await _cache_get(db, cache_key)
    if cached is not None:
        payload = cached
    else:
        try:
            payload = await get_json(COMPLAINTS_URL, {"make": make, "model": model, "modelYear": year})
        except NHTSAClientError:
            return []
        await _cache_put(db, cache_key, payload)

    totals: dict[str, dict[str, int]] = {}
    for row in payload.get("results", []):
        component = row.get("components", "UNKNOWN")
        bucket = totals.setdefault(component, {"count": 0, "crash": 0, "fire": 0})
        bucket["count"] += 1
        bucket["crash"] += 1 if row.get("crash") else 0
        bucket["fire"] += 1 if row.get("fire") else 0

    summaries = [
        ComplaintComponentSummary(component=c, count=v["count"], crash_count=v["crash"], fire_count=v["fire"])
        for c, v in totals.items()
    ]
    summaries.sort(key=lambda s: s.count, reverse=True)
    return summaries[:3]


async def decode_vin(db: AsyncSession, vin: str) -> dict | None:
    cache_key = f"vin:{vin.upper()}"
    cached = await _cache_get(db, cache_key)
    if cached is not None:
        return cached

    try:
        payload = await get_json(VPIC_DECODE_URL.format(vin=vin))
    except NHTSAClientError:
        return None

    results = {row["Variable"]: row["Value"] for row in payload.get("Results", []) if row.get("Value")}
    decoded = {
        "make": results.get("Make"),
        "model": results.get("Model"),
        "model_year": results.get("Model Year"),
        "error_text": results.get("Error Text"),
    }
    if not decoded.get("make"):
        return None

    await _cache_put(db, cache_key, decoded)
    return decoded
