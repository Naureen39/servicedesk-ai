"""Public, unauthenticated data endpoints (Section 2.5): vehicle catalog, recalls, complaints.

Backed by the tables Phase 1 loaded (`vehicle_catalog`, `recall_campaigns`,
`complaints_monthly`) so these return real NHTSA/EPA-derived data, not stubs. VIN decoding
proxies the live NHTSA vPIC API per the plan's note that make/model spelling must be resolved
through NHTSA's own endpoints, never raw user text.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.base import get_db
from app.db.models.business import ContactMessage, Location, ServiceCatalog
from app.db.models.knowledge import ComplaintsMonthly, RecallCampaign, VehicleCatalog
from app.schemas.public import (
    ComplaintSummaryOut,
    ContactRequest,
    ContactResponse,
    LiveRecallOut,
    LocationOut,
    RecallOut,
    ServiceCatalogOut,
)

router = APIRouter(tags=["public"])

VPIC_DECODE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"


@router.get("/locations", response_model=list[LocationOut])
async def list_locations(db: AsyncSession = Depends(get_db)) -> list[Location]:
    result = await db.execute(select(Location).order_by(Location.location_id))
    return list(result.scalars().all())


@router.get("/services", response_model=list[ServiceCatalogOut])
async def list_services(category: str | None = Query(default=None), db: AsyncSession = Depends(get_db)) -> list[ServiceCatalog]:
    stmt = select(ServiceCatalog).order_by(ServiceCatalog.category, ServiceCatalog.name)
    if category is not None:
        stmt = stmt.where(ServiceCatalog.category == category)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/services/{code}", response_model=ServiceCatalogOut)
async def get_service(code: str, db: AsyncSession = Depends(get_db)) -> ServiceCatalog:
    result = await db.execute(select(ServiceCatalog).where(ServiceCatalog.code == code))
    service = result.scalar_one_or_none()
    if service is None:
        raise AppError(404, "Service not found", type_slug="https://meridian.example/problems/not-found")
    return service


@router.post("/contact", response_model=ContactResponse, status_code=201)
async def submit_contact(payload: ContactRequest, db: AsyncSession = Depends(get_db)) -> ContactResponse:
    message_id = f"MSG-{uuid.uuid4().hex[:10].upper()}"
    db.add(
        ContactMessage(
            message_id=message_id,
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            location_id=payload.location_id,
            subject=payload.subject,
            message=payload.message,
            status="open",
            created_at=datetime.now(UTC),
        )
    )
    await db.commit()
    return ContactResponse(message_id=message_id, status="open")


@router.get("/nhtsa/makes", response_model=list[str])
async def live_nhtsa_makes(year: int = Query(...)) -> list[str]:
    """Section 7.4 Home: "Year, Make, Model dropdowns populated live from NHTSA products
    endpoints" -- hits the real NHTSA products/vehicle/makes endpoint (same client as the
    Phase 5/6 dialog pipeline), not the locally-cached historical vehicle_catalog table."""
    from app.services.nhtsa.client import get_json
    from app.services.nhtsa.resolver import PRODUCTS_MAKES_URL

    data = await get_json(PRODUCTS_MAKES_URL, {"modelYear": year, "issueType": "r"})
    makes = sorted({row["make"] for row in data.get("results", [])})
    return makes


@router.get("/nhtsa/models", response_model=list[str])
async def live_nhtsa_models(year: int = Query(...), make: str = Query(...)) -> list[str]:
    from app.services.nhtsa.client import get_json
    from app.services.nhtsa.resolver import PRODUCTS_MODELS_URL

    data = await get_json(PRODUCTS_MODELS_URL, {"modelYear": year, "make": make, "issueType": "r"})
    models = sorted({row["model"] for row in data.get("results", [])})
    return models


@router.get("/nhtsa/recalls", response_model=list[LiveRecallOut])
async def live_nhtsa_recalls(
    year: int = Query(...), make: str = Query(...), model: str = Query(...), db: AsyncSession = Depends(get_db)
) -> list[LiveRecallOut]:
    """Real live NHTSA recallsByVehicle lookup (Phase 7 DoD: "recall lookup returns live NHTSA
    data"), reusing the exact same cached service the chat/voice channels call."""
    from app.services.nhtsa.service import get_recalls

    records = await get_recalls(db, year, make, model)
    return [
        LiveRecallOut(
            campaign_number=r.campaign_number, component=r.component, summary=r.summary,
            consequence=r.consequence, remedy=r.remedy, report_date=r.report_date,
        )
        for r in records
    ]


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
