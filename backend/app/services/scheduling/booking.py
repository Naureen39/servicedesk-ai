"""Booking, reschedule, cancel, and .ics generation (Section 5.2).

`create_booking` relies on the DB-level exclusion constraints (see the Phase 5 Alembic
migration) as the real source of truth for "exactly one booking wins" under concurrency: two
concurrent transactions can both pass the in-memory availability check and both attempt to
INSERT the same technician/bay/time; the loser's INSERT is rejected by Postgres itself with an
IntegrityError, which this module turns into a typed SlotConflictError the caller can retry
against the next offered slot. `SELECT ... FOR UPDATE` alone cannot provide this guarantee for
a brand-new INSERT (there is no existing row to lock), which is why the plan lists the
exclusion constraint as the alternative to it.
"""

from __future__ import annotations

import random
import string
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.business import Appointment
from app.services.customers import decrypt_value
from app.services.scheduling.availability import SlotOffer

SAME_DAY_LEAD_HOURS = 2


class SlotConflictError(Exception):
    """Raised when the exclusion constraint rejects a booking because another request won
    the same technician/bay/time slot first (Phase 5 DoD: 50 parallel bookings for the same
    slot, exactly one succeeds)."""


class LeadTimeError(Exception):
    """Section 5.2: "same-day bookings need a 2 h lead time"."""


def generate_reference_code() -> str:
    return "MRD-" + "".join(random.choices(string.digits, k=6))


async def create_booking(
    db: AsyncSession,
    *,
    customer_id: str,
    vehicle_id: str,
    service_code: str,
    offer: SlotOffer,
    channel: str,
) -> Appointment:
    now = datetime.now(UTC)
    if offer.start.date() == now.date() and offer.start < now + timedelta(hours=SAME_DAY_LEAD_HOURS):
        raise LeadTimeError("Same-day bookings require at least 2 hours' notice")

    appointment = Appointment(
        appointment_id=f"APT-{uuid.uuid4().hex[:10].upper()}",
        reference_code=generate_reference_code(),
        customer_id=customer_id,
        vehicle_id=vehicle_id,
        location_id=offer.location_id,
        technician_id=offer.technician_id,
        bay_number=offer.bay_number,
        service_code=service_code,
        scheduled_start=offer.start,
        scheduled_end=offer.end,
        booked_at=now,
        status="booked",
        channel_created=channel,
        booked_via_engine=True,
    )
    db.add(appointment)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise SlotConflictError(f"{offer.technician_id} bay {offer.bay_number} at {offer.start} was just booked") from exc

    return appointment


async def verify_by_reference_and_last4(
    db: AsyncSession, reference_code: str, last4_digits: str
) -> Appointment | None:
    """Section 5.2: "reschedule and cancel via reference code plus last 4 phone digits"."""
    from sqlalchemy import select

    from app.db.models.business import Customer

    result = await db.execute(select(Appointment).where(Appointment.reference_code == reference_code))
    appointment = result.scalar_one_or_none()
    if appointment is None:
        return None

    customer_result = await db.execute(select(Customer).where(Customer.customer_id == appointment.customer_id))
    customer = customer_result.scalar_one_or_none()
    if customer is None or customer.phone_encrypted is None:
        return None

    phone = await decrypt_value(db, customer.phone_encrypted)
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if digits[-4:] != last4_digits:
        return None

    return appointment


async def cancel_appointment(db: AsyncSession, appointment: Appointment) -> None:
    appointment.status = "cancelled"
    await db.flush()


async def reschedule_appointment(db: AsyncSession, appointment: Appointment, new_offer: SlotOffer) -> Appointment:
    now = datetime.now(UTC)
    if new_offer.start.date() == now.date() and new_offer.start < now + timedelta(hours=SAME_DAY_LEAD_HOURS):
        raise LeadTimeError("Same-day bookings require at least 2 hours' notice")

    appointment.scheduled_start = new_offer.start
    appointment.scheduled_end = new_offer.end
    appointment.technician_id = new_offer.technician_id
    appointment.bay_number = new_offer.bay_number
    appointment.location_id = new_offer.location_id
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise SlotConflictError(
            f"{new_offer.technician_id} bay {new_offer.bay_number} at {new_offer.start} was just booked"
        ) from exc
    return appointment


def generate_ics(appointment: Appointment, service_name: str, location_name: str, location_address: str) -> str:
    """Section 5.2: ".ics calendar file download"."""

    def fmt(dt: datetime) -> str:
        return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")

    now = datetime.now(UTC)
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Meridian Auto Group//Meridian Assist//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{appointment.appointment_id}@meridianauto.example\r\n"
        f"DTSTAMP:{fmt(now)}\r\n"
        f"DTSTART:{fmt(appointment.scheduled_start)}\r\n"
        f"DTEND:{fmt(appointment.scheduled_end)}\r\n"
        f"SUMMARY:{service_name} -- Meridian Auto Group\r\n"
        f"LOCATION:{location_name}, {location_address}\r\n"
        f"DESCRIPTION:Confirmation code {appointment.reference_code}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
