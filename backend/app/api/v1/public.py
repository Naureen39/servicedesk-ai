"""Public, unauthenticated data endpoints (Section 2.5): vehicle catalog, recalls, complaints.

Backed by the tables Phase 1 loaded (`vehicle_catalog`, `recall_campaigns`,
`complaints_monthly`) so these return real NHTSA/EPA-derived data, not stubs. VIN decoding
proxies the live NHTSA vPIC API per the plan's note that make/model spelling must be resolved
through NHTSA's own endpoints, never raw user text.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.base import get_db
from app.db.models.knowledge import ComplaintsMonthly, RecallCampaign, VehicleCatalog
from app.schemas.public import ComplaintSummaryOut, RecallOut

router = APIRouter(tags=["public"])

VPIC_DECODE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"


@router.get("/vehicles/years", response_model=list[int])
async def vehicle_years(db: AsyncSession = Depends(get_db)) -> list[int]:
    result = await db.execute(select(distinct(VehicleCatalog.year)).order_by(VehicleCatalog.year.desc()))
    return [row[0] for row in result.all()]


@router.get("/vehicles/makes", response_model=list[str])
async def vehicle_makes(year: int = Query(...), db: AsyncSession = Depends(get_db)) -> list[str]:
    result = await db.execute(
        select(distinct(VehicleCatalog.make)).where(VehicleCatalog.year == year).order_by(VehicleCatalog.make)
    )
    return [row[0] for row in result.all()]


@router.get("/vehicles/models", response_model=list[str])
async def vehicle_models(year: int = Query(...), make: str = Query(...), db: AsyncSession = Depends(get_db)) -> list[str]:
    result = await db.execute(
        select(distinct(VehicleCatalog.model))
        .where(VehicleCatalog.year == year, VehicleCatalog.make == make)
        .order_by(VehicleCatalog.model)
    )
    return [row[0] for row in result.all()]


@router.get("/vehicles/decode/{vin}")
async def decode_vin(vin: str) -> dict:
    if len(vin) != 17:
        raise AppError(400, "VIN must be 17 characters", type_slug="https://meridian.example/problems/invalid-vin")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(VPIC_DECODE_URL.format(vin=vin))
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(502, f"NHTSA vPIC lookup failed: {exc}", type_slug="https://meridian.example/problems/upstream-error") from exc
    payload = resp.json()
    results = {row["Variable"]: row["Value"] for row in payload.get("Results", []) if row.get("Value")}
    return {
        "vin": vin,
        "make": results.get("Make"),
        "model": results.get("Model"),
        "model_year": results.get("Model Year"),
        "raw": results,
    }


@router.get("/recalls", response_model=list[RecallOut])
async def list_recalls(
    year: int | None = Query(default=None),
    make: str | None = Query(default=None),
    model: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[RecallOut]:
    stmt = select(RecallCampaign)
    if year is not None:
        stmt = stmt.where(RecallCampaign.model_year == year)
    if make is not None:
        stmt = stmt.where(RecallCampaign.make == make.upper())
    if model is not None:
        stmt = stmt.where(RecallCampaign.model.ilike(f"%{model}%"))
    stmt = stmt.order_by(RecallCampaign.report_date.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/complaints/summary", response_model=list[ComplaintSummaryOut])
async def complaints_summary(
    year: int | None = Query(default=None),
    make: str | None = Query(default=None),
    model: str | None = Query(default=None),
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[ComplaintSummaryOut]:
    stmt = select(
        ComplaintsMonthly.make,
        ComplaintsMonthly.model,
        ComplaintsMonthly.model_year,
        ComplaintsMonthly.component,
        func.sum(ComplaintsMonthly.count).label("total_count"),
        func.sum(ComplaintsMonthly.crash).label("crash_count"),
        func.sum(ComplaintsMonthly.fire).label("fire_count"),
        func.sum(ComplaintsMonthly.injured).label("injured_count"),
    )
    if year is not None:
        stmt = stmt.where(ComplaintsMonthly.model_year == year)
    if make is not None:
        stmt = stmt.where(ComplaintsMonthly.make == make.upper())
    if model is not None:
        stmt = stmt.where(ComplaintsMonthly.model.ilike(f"%{model}%"))
    stmt = (
        stmt.group_by(ComplaintsMonthly.make, ComplaintsMonthly.model, ComplaintsMonthly.model_year, ComplaintsMonthly.component)
        .order_by(func.sum(ComplaintsMonthly.count).desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        ComplaintSummaryOut(
            make=row.make,
            model=row.model,
            model_year=row.model_year,
            component=row.component,
            total_count=row.total_count or 0,
            crash_count=row.crash_count or 0,
            fire_count=row.fire_count or 0,
            injured_count=row.injured_count or 0,
        )
        for row in result.all()
    ]
