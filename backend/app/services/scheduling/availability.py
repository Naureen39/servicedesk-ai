"""Real availability computation (Section 5.2), replacing the Phase 4 dialog-flow stub.

Computed from shift_templates, technician skill_level, bay bay_type, existing appointments,
service duration from the catalog, and holidays -- returns the 3 earliest matching slots,
spread across different days when possible. Business rules: same-day bookings need a 2 hour
lead time; Saturday capacity is capped at 90%; recall work requires the service's
parts_available flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.business import Appointment, Bay, Holiday, ServiceCatalog, ShiftTemplate, Technician

SLOT_STEP_MINUTES = 15
SEARCH_WINDOW_DAYS = 21
MAX_OFFERS = 3
SAME_DAY_LEAD_HOURS = 2
SATURDAY_CAPACITY_CAP = 0.90

SKILL_RANK = {"A": 0, "B": 1, "C": 2}  # lower = more skilled; A qualifies for anything


@dataclass
class SlotOffer:
    start: datetime
    end: datetime
    technician_id: str
    bay_number: int
    location_id: int


class PartsUnavailableError(Exception):
    """Section 5.2: "recall work requires parts availability flag"."""


def _skill_qualifies(technician_level: str | None, required_level: str | None) -> bool:
    if not required_level:
        return True
    tech_rank = SKILL_RANK.get(technician_level or "C", 2)
    required_rank = SKILL_RANK.get(required_level, 2)
    return tech_rank <= required_rank


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")[:2]
    return time(int(hour), int(minute))


async def find_available_slots(
    db: AsyncSession,
    location_id: int,
    service_code: str,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    max_offers: int = MAX_OFFERS,
) -> list[SlotOffer]:
    service_result = await db.execute(select(ServiceCatalog).where(ServiceCatalog.code == service_code))
    service = service_result.scalar_one_or_none()
    if service is None:
        return []
    if service.category == "Recall" and not service.parts_available:
        raise PartsUnavailableError(f"Parts are not currently available for {service.name}")

    duration = timedelta(minutes=int(service.duration_min or 60))
    now = datetime.now(UTC)
    window_start = max(window_start or now, now)
    window_end = window_end or (window_start + timedelta(days=SEARCH_WINDOW_DAYS))

    technicians_result = await db.execute(select(Technician).where(Technician.location_id == location_id))
    technicians = [t for t in technicians_result.scalars().all() if _skill_qualifies(t.skill_level, service.skill_level)]
    if not technicians:
        return []
    technician_ids = [t.technician_id for t in technicians]

    shifts_result = await db.execute(select(ShiftTemplate).where(ShiftTemplate.technician_id.in_(technician_ids)))
    shifts_by_tech_day: dict[tuple[str, int], ShiftTemplate] = {
        (s.technician_id, s.weekday): s for s in shifts_result.scalars().all()
    }

    bays_result = await db.execute(
        select(Bay).where(Bay.location_id == location_id, Bay.bay_type == (service.bay_type or "general"))
    )
    bays = list(bays_result.scalars().all())
    if not bays:
        # Fall back to any bay at the location rather than offering nothing, if the catalog's
        # bay_type has no dedicated bays at this particular location.
        bays_result = await db.execute(select(Bay).where(Bay.location_id == location_id))
        bays = list(bays_result.scalars().all())
    if not bays:
        return []
    bay_numbers = [b.bay_number for b in bays]

    holidays_result = await db.execute(
        select(Holiday.date).where(Holiday.date >= window_start.date(), Holiday.date <= window_end.date())
    )
    holiday_dates = {row[0] for row in holidays_result.all()}

    existing_result = await db.execute(
        select(Appointment.technician_id, Appointment.bay_number, Appointment.scheduled_start, Appointment.scheduled_end)
        .where(
            Appointment.location_id == location_id,
            Appointment.status.in_(("booked", "completed")),
            Appointment.scheduled_start < window_end,
            Appointment.scheduled_end > window_start,
        )
    )
    existing = list(existing_result.all())

    def technician_busy(technician_id: str, start: datetime, end: datetime) -> bool:
        return any(tid == technician_id and start < e_end and end > e_start for tid, _b, e_start, e_end in existing)

    def bay_busy(bay_number: int, start: datetime, end: datetime) -> bool:
        return any(bn == bay_number and start < e_end and end > e_start for _t, bn, e_start, e_end in existing)

    def saturday_at_capacity(day: date) -> bool:
        day_start = datetime.combine(day, time.min, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        booked_count = sum(1 for _t, _b, s, _e in existing if day_start <= s < day_end)
        total_capacity = sum(
            1
            for t in technician_ids
            if (t, day.weekday()) in shifts_by_tech_day
        ) * len(bay_numbers)
        if total_capacity == 0:
            return True
        return (booked_count / total_capacity) >= SATURDAY_CAPACITY_CAP

    offers: list[SlotOffer] = []
    day = window_start.date()
    while day <= window_end.date() and len(offers) < max_offers:
        if day.weekday() == 6 or day in holiday_dates:
            day += timedelta(days=1)
            continue
        if day.weekday() == 5 and saturday_at_capacity(day):
            day += timedelta(days=1)
            continue

        day_offer: SlotOffer | None = None
        for technician in technicians:
            shift = shifts_by_tech_day.get((technician.technician_id, day.weekday()))
            if shift is None or not shift.start_time or not shift.end_time:
                continue
            shift_start = datetime.combine(day, _parse_time(shift.start_time), tzinfo=UTC)
            shift_end = datetime.combine(day, _parse_time(shift.end_time), tzinfo=UTC)

            earliest = max(shift_start, window_start)
            if day == now.date():
                earliest = max(earliest, now + timedelta(hours=SAME_DAY_LEAD_HOURS))
            # Round up to the next slot-step boundary.
            minutes_over = earliest.minute % SLOT_STEP_MINUTES
            if minutes_over or earliest.second:
                earliest += timedelta(minutes=SLOT_STEP_MINUTES - minutes_over, seconds=-earliest.second, microseconds=-earliest.microsecond)

            candidate = earliest
            while candidate + duration <= shift_end:
                if not technician_busy(technician.technician_id, candidate, candidate + duration):
                    free_bay = next((b for b in bay_numbers if not bay_busy(b, candidate, candidate + duration)), None)
                    if free_bay is not None:
                        day_offer = SlotOffer(
                            start=candidate, end=candidate + duration,
                            technician_id=technician.technician_id, bay_number=free_bay,
                            location_id=location_id,
                        )
                        break
                candidate += timedelta(minutes=SLOT_STEP_MINUTES)
            if day_offer is not None:
                break

        if day_offer is not None:
            offers.append(day_offer)
            # Reserve this slot in the in-memory conflict set so a later day in this same
            # search doesn't also offer the same technician/bay pair a second time.
            existing.append((day_offer.technician_id, day_offer.bay_number, day_offer.start, day_offer.end))

        day += timedelta(days=1)

    return offers[:max_offers]
