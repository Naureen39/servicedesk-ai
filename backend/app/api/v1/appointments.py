"""Appointment endpoints (Section 2.5). Listing/patch/cancel by staff are real, RBAC- and
location-scoped queries against the appointments table Phase 1 populated. Availability and
public booking are the real Phase 5 scheduling engine: bay/technician conflict checking,
DB-enforced no-double-booking, business rules (same-day lead time, Saturday capacity, recall
parts availability), reference-code + last-4-digit reschedule/cancel, and .ics download.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.permissions import PERM_APPOINTMENTS_READ, PERM_APPOINTMENTS_WRITE
from app.core.security import lookup_hash
from app.db.base import get_db
from app.db.models.business import Appointment, Customer, Location, ServiceCatalog, Vehicle
from app.schemas.appointments import (
    AppointmentCreateRequest,
    AppointmentCreateResponse,
    AppointmentOut,
    AppointmentPatch,
    AppointmentVerifyRequest,
    SlotOfferOut,
)
from app.services.audit import record_audit
from app.services.customers import encrypt_value
from app.services.scheduling.availability import PartsUnavailableError, find_available_slots
from app.services.scheduling.booking import (
    LeadTimeError,
    SlotConflictError,
    create_booking,
    generate_ics,
    verify_by_reference_and_last4,
)
from app.services.scheduling.booking import (
    cancel_appointment as service_cancel_appointment,
)

from .deps import CurrentUser, get_client_ip, location_filter, require_permission

router = APIRouter(tags=["appointments"])


@router.get("/availability", response_model=list[SlotOfferOut])
async def get_availability(
    location_id: int = Query(...),
    service_code: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> list[SlotOfferOut]:
    try:
        offers = await find_available_slots(db, location_id, service_code)
    except PartsUnavailableError as exc:
        raise AppError(409, str(exc), type_slug="https://meridian.example/problems/parts-unavailable") from exc
    return [SlotOfferOut(start=o.start, end=o.end) for o in offers]


async def _find_or_create_customer_and_vehicle(db: AsyncSession, payload: AppointmentCreateRequest) -> tuple[str, str]:
    phone_hash = lookup_hash(payload.phone)
    result = await db.execute(select(Customer.customer_id).where(Customer.phone_hash == phone_hash).limit(1))
    customer_id = result.scalar_one_or_none()

    if customer_id is None:
        customer_id = f"CUST-{uuid.uuid4().hex[:10].upper()}"
        first_name, _, last_name = payload.name.partition(" ")
        db.add(
            Customer(
                customer_id=customer_id,
                first_name=first_name or None,
                last_name=last_name or None,
                phone_encrypted=await encrypt_value(db, payload.phone),
                email_encrypted=await encrypt_value(db, payload.email) if payload.email else None,
                phone_hash=phone_hash,
                email_hash=lookup_hash(payload.email) if payload.email else None,
                created_at=datetime.now(UTC),
            )
        )
        await db.flush()

    vehicle_result = await db.execute(
        select(Vehicle.vehicle_id).where(
            Vehicle.customer_id == customer_id, Vehicle.make == payload.vehicle.make, Vehicle.model == payload.vehicle.model,
            Vehicle.year == payload.vehicle.year,
        )
    )
    vehicle_id = vehicle_result.scalar_one_or_none()
    if vehicle_id is None:
        vehicle_id = f"VEH-{uuid.uuid4().hex[:10].upper()}"
        db.add(
            Vehicle(
                vehicle_id=vehicle_id, customer_id=customer_id, year=payload.vehicle.year,
                make=payload.vehicle.make, model=payload.vehicle.model, vin=payload.vehicle.vin,
            )
        )
        await db.flush()

    return customer_id, vehicle_id


@router.post("/appointments", response_model=AppointmentCreateResponse, status_code=201)
async def create_appointment(
    payload: AppointmentCreateRequest, db: AsyncSession = Depends(get_db)
) -> AppointmentCreateResponse:
    service_result = await db.execute(select(ServiceCatalog).where(ServiceCatalog.code == payload.service_code))
    service = service_result.scalar_one_or_none()
    if service is None:
        raise AppError(400, "Unknown service_code", type_slug="https://meridian.example/problems/validation-error")

    offers = await find_available_slots(
        db, payload.location_id, payload.service_code, window_start=payload.scheduled_start
    )
    offer = next((o for o in offers if o.start == payload.scheduled_start), None)
    if offer is None:
        raise AppError(
            409,
            "That time is no longer available; please request availability again",
            type_slug="https://meridian.example/problems/slot-unavailable",
        )

    customer_id, vehicle_id = await _find_or_create_customer_and_vehicle(db, payload)

    try:
        appointment = await create_booking(
            db, customer_id=customer_id, vehicle_id=vehicle_id, service_code=payload.service_code,
            offer=offer, channel="web",
        )
    except SlotConflictError as exc:
        raise AppError(409, str(exc), type_slug="https://meridian.example/problems/slot-unavailable") from exc
    except LeadTimeError as exc:
        raise AppError(400, str(exc), type_slug="https://meridian.example/problems/validation-error") from exc

    await db.commit()
    return AppointmentCreateResponse(
        appointment_id=appointment.appointment_id, reference_code=appointment.reference_code,
        scheduled_start=appointment.scheduled_start, scheduled_end=appointment.scheduled_end,
        status=appointment.status,
    )


@router.post("/appointments/verify", response_model=AppointmentOut)
async def verify_appointment(payload: AppointmentVerifyRequest, db: AsyncSession = Depends(get_db)) -> Appointment:
    appointment = await verify_by_reference_and_last4(db, payload.reference_code, payload.phone_last4)
    if appointment is None:
        raise AppError(404, "No appointment matches that confirmation code and phone digits", type_slug="https://meridian.example/problems/not-found")
    return appointment


@router.delete("/appointments/by-reference/{reference_code}", status_code=204)
async def cancel_appointment_by_reference(
    reference_code: str, phone_last4: str = Query(..., min_length=4, max_length=4), db: AsyncSession = Depends(get_db)
) -> None:
    appointment = await verify_by_reference_and_last4(db, reference_code, phone_last4)
    if appointment is None:
        raise AppError(404, "No appointment matches that confirmation code and phone digits", type_slug="https://meridian.example/problems/not-found")
    await service_cancel_appointment(db, appointment)
    await db.commit()


@router.get("/appointments/by-reference/{reference_code}/calendar.ics")
async def download_calendar(
    reference_code: str, phone_last4: str = Query(..., min_length=4, max_length=4), db: AsyncSession = Depends(get_db)
) -> Response:
    appointment = await verify_by_reference_and_last4(db, reference_code, phone_last4)
    if appointment is None:
        raise AppError(404, "No appointment matches that confirmation code and phone digits", type_slug="https://meridian.example/problems/not-found")

    service_result = await db.execute(select(ServiceCatalog.name).where(ServiceCatalog.code == appointment.service_code))
    service_name = service_result.scalar_one_or_none() or "Service Appointment"
    location_result = await db.execute(select(Location).where(Location.location_id == appointment.location_id))
    location = location_result.scalar_one_or_none()

    ics = generate_ics(
        appointment, service_name,
        location.name if location else "Meridian Auto Group",
        location.address if location else "",
    )
    return Response(
        content=ics, media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={reference_code}.ics"},
    )


@router.get("/appointments", response_model=list[AppointmentOut])
async def list_appointments(
    location_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission(PERM_APPOINTMENTS_READ)),
    db: AsyncSession = Depends(get_db),
) -> list[Appointment]:
    scoped_location_id = location_filter(user, location_id)

    stmt = select(Appointment)
    if scoped_location_id is not None:
        stmt = stmt.where(Appointment.location_id == scoped_location_id)
    if status is not None:
        stmt = stmt.where(Appointment.status == status)
    stmt = stmt.order_by(Appointment.scheduled_start.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.patch("/appointments/{appointment_id}", response_model=AppointmentOut)
async def patch_appointment(
    appointment_id: str,
    payload: AppointmentPatch,
    user: CurrentUser = Depends(require_permission(PERM_APPOINTMENTS_WRITE)),
    db: AsyncSession = Depends(get_db),
    ip: str = Depends(get_client_ip),
) -> Appointment:
    result = await db.execute(select(Appointment).where(Appointment.appointment_id == appointment_id))
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise AppError(404, "Appointment not found", type_slug="https://meridian.example/problems/not-found")

    scoped_location_id = location_filter(user, appointment.location_id)
    if scoped_location_id is not None and appointment.location_id != scoped_location_id:
        raise AppError(403, "Appointment is outside your assigned location", type_slug="https://meridian.example/problems/forbidden")

    before = {"status": appointment.status, "technician_id": appointment.technician_id, "bay_number": appointment.bay_number}
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(appointment, field, value)

    await record_audit(
        db,
        actor_user_id=user.id,
        action="appointment.update",
        entity_type="appointment",
        entity_id=appointment_id,
        before=before,
        after=changes,
        ip=ip,
    )
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.delete("/appointments/{appointment_id}", status_code=204)
async def cancel_appointment(
    appointment_id: str,
    user: CurrentUser = Depends(require_permission(PERM_APPOINTMENTS_WRITE)),
    db: AsyncSession = Depends(get_db),
    ip: str = Depends(get_client_ip),
) -> None:
    result = await db.execute(select(Appointment).where(Appointment.appointment_id == appointment_id))
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise AppError(404, "Appointment not found", type_slug="https://meridian.example/problems/not-found")

    scoped_location_id = location_filter(user, appointment.location_id)
    if scoped_location_id is not None and appointment.location_id != scoped_location_id:
        raise AppError(403, "Appointment is outside your assigned location", type_slug="https://meridian.example/problems/forbidden")

    await db.execute(
        update(Appointment).where(Appointment.appointment_id == appointment_id).values(status="cancelled")
    )
    await record_audit(
        db,
        actor_user_id=user.id,
        action="appointment.cancel",
        entity_type="appointment",
        entity_id=appointment_id,
        before={"status": appointment.status},
        after={"status": "cancelled"},
        ip=ip,
    )
    await db.commit()
