"""Appointment endpoints (Section 2.5). Listing/patch/cancel by staff are real, RBAC- and
location-scoped queries against the appointments table Phase 1 populated. Availability
computation and public booking are the Phase 5 scheduling engine (bay/technician conflict
checking) and return 501 here.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.permissions import PERM_APPOINTMENTS_READ, PERM_APPOINTMENTS_WRITE
from app.db.base import get_db
from app.db.models.business import Appointment
from app.schemas.appointments import AppointmentOut, AppointmentPatch
from app.services.audit import record_audit

from .deps import CurrentUser, get_client_ip, location_filter, require_permission

router = APIRouter(tags=["appointments"])


@router.get("/availability")
async def get_availability(
    location_id: int = Query(...),
    service_code: str = Query(...),
    window_start: datetime = Query(...),
    window_end: datetime = Query(...),
) -> dict:
    raise AppError(
        501,
        "Availability computation is implemented in Phase 5 (Scheduling Engine)",
        type_slug="https://meridian.example/problems/not-implemented",
    )


@router.post("/appointments", status_code=201)
async def create_appointment() -> dict:
    raise AppError(
        501,
        "Appointment booking is implemented in Phase 5 (Scheduling Engine)",
        type_slug="https://meridian.example/problems/not-implemented",
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
