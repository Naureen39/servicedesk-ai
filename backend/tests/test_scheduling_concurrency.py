"""Phase 5 DoD: concurrency test with 50 parallel bookings for the same slot produces exactly
one success. This exercises the real GiST exclusion constraints added in the Phase 5 migration
(app/services/scheduling/booking.py's docstring explains why SELECT ... FOR UPDATE alone can't
give this guarantee for a brand-new INSERT) -- 50 separate DB connections race to book the
identical technician/bay/time slot, and Postgres itself must reject 49 of them.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.db.base import async_session_factory
from app.services.scheduling.availability import SlotOffer
from app.services.scheduling.booking import SlotConflictError, create_booking

pytestmark = pytest.mark.asyncio

CONCURRENT_ATTEMPTS = 50


@pytest.fixture
async def customer_and_vehicle():
    customer_id = f"CUST-CONC-{uuid.uuid4().hex[:8].upper()}"
    vehicle_id = f"VEH-CONC-{uuid.uuid4().hex[:8].upper()}"
    async with async_session_factory() as db:
        await db.execute(
            text("INSERT INTO customers (customer_id, first_name, last_name, created_at) VALUES (:cid, 'Conc', 'Test', now())"),
            {"cid": customer_id},
        )
        await db.execute(
            text("INSERT INTO vehicles (vehicle_id, customer_id, year, make, model) VALUES (:vid, :cid, 2022, 'Toyota', 'Camry')"),
            {"vid": vehicle_id, "cid": customer_id},
        )
        await db.commit()
    yield customer_id, vehicle_id
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM appointments WHERE customer_id = :cid"), {"cid": customer_id})
        await db.execute(text("DELETE FROM vehicles WHERE vehicle_id = :vid"), {"vid": vehicle_id})
        await db.execute(text("DELETE FROM customers WHERE customer_id = :cid"), {"cid": customer_id})
        await db.commit()


async def _attempt_booking(customer_id: str, vehicle_id: str, offer: SlotOffer) -> bool:
    """Each attempt uses its own session/connection, so this genuinely exercises 50 concurrent
    Postgres transactions, not 50 calls serialized onto one connection."""
    async with async_session_factory() as db:
        try:
            await create_booking(
                db, customer_id=customer_id, vehicle_id=vehicle_id, service_code="OIL-CONV",
                offer=offer, channel="chat",
            )
            await db.commit()
            return True
        except SlotConflictError:
            return False


async def test_fifty_parallel_bookings_for_the_same_slot_exactly_one_succeeds(customer_and_vehicle):
    customer_id, vehicle_id = customer_and_vehicle
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(days=10, hours=9)
    offer = SlotOffer(start=start, end=start + timedelta(minutes=30), technician_id="T001", bay_number=1, location_id=1)

    results = await asyncio.gather(
        *[_attempt_booking(customer_id, vehicle_id, offer) for _ in range(CONCURRENT_ATTEMPTS)]
    )

    successes = sum(results)
    assert successes == 1, f"expected exactly 1 success among {CONCURRENT_ATTEMPTS} parallel bookings, got {successes}"

    async with async_session_factory() as db:
        from app.db.models.business import Appointment

        result = await db.execute(
            select(Appointment).where(
                Appointment.technician_id == "T001",
                Appointment.scheduled_start == start,
                Appointment.status == "booked",
            )
        )
        rows = result.scalars().all()
    assert len(rows) == 1, f"expected exactly 1 appointment row for this slot in the DB, found {len(rows)}"
