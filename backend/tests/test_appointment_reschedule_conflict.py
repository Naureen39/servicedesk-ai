"""Phase 8 Appointments: staff-side reschedule ("drag to reschedule with conflict validation")
now supports moving `scheduled_start`/`scheduled_end` through PATCH /appointments/{id}, real
conflict validation is the same DB exclusion constraint the customer-facing booking flow uses
(not a duplicated application-level check)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db.base import async_session_factory
from app.services.scheduling.availability import SlotOffer
from app.services.scheduling.booking import create_booking

from .conftest import create_user, login

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def two_real_appointments():
    customer_id = f"CUST-RS-{uuid.uuid4().hex[:8].upper()}"
    vehicle_id = f"VEH-RS-{uuid.uuid4().hex[:8].upper()}"
    async with async_session_factory() as db:
        await db.execute(text("INSERT INTO customers (customer_id, first_name, last_name, created_at) VALUES (:cid, 'Resched', 'Test', now())"), {"cid": customer_id})
        await db.execute(text("INSERT INTO vehicles (vehicle_id, customer_id, year, make, model) VALUES (:vid, :cid, 2021, 'Honda', 'Civic')"), {"vid": vehicle_id, "cid": customer_id})
        await db.commit()

    base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(days=14, hours=9)
    async with async_session_factory() as db:
        appt_a = await create_booking(
            db, customer_id=customer_id, vehicle_id=vehicle_id, service_code="OIL-CONV",
            offer=SlotOffer(start=base, end=base + timedelta(minutes=30), technician_id="T001", bay_number=1, location_id=1),
            channel="web",
        )
        appt_b = await create_booking(
            db, customer_id=customer_id, vehicle_id=vehicle_id, service_code="OIL-CONV",
            offer=SlotOffer(start=base + timedelta(hours=2), end=base + timedelta(hours=2, minutes=30), technician_id="T001", bay_number=1, location_id=1),
            channel="web",
        )
        await db.commit()
        appt_a_id, appt_b_id = appt_a.appointment_id, appt_b.appointment_id

    yield appt_a_id, appt_b_id, base

    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM appointments WHERE customer_id = :cid"), {"cid": customer_id})
        await db.execute(text("DELETE FROM vehicles WHERE vehicle_id = :vid"), {"vid": vehicle_id})
        await db.execute(text("DELETE FROM customers WHERE customer_id = :cid"), {"cid": customer_id})
        await db.commit()


async def test_reschedule_into_a_real_conflict_is_rejected(client, auth_headers, two_real_appointments):
    _appt_a_id, appt_b_id, base = two_real_appointments
    advisor = await create_user("advisor-resched@example.com", "pw", "service_advisor", mfa=False, location_id=1)
    token = await login(client, advisor.email, "pw")

    # Move appointment B onto exactly appointment A's technician/bay/time -- a real collision.
    resp = await client.patch(
        f"/api/v1/appointments/{appt_b_id}",
        json={"scheduled_start": base.isoformat(), "scheduled_end": (base + timedelta(minutes=30)).isoformat()},
        headers=auth_headers(token),
    )
    assert resp.status_code == 409, resp.text


async def test_reschedule_into_a_free_slot_succeeds(client, auth_headers, two_real_appointments):
    _appt_a_id, appt_b_id, base = two_real_appointments
    advisor = await create_user("advisor-resched2@example.com", "pw", "service_advisor", mfa=False, location_id=1)
    token = await login(client, advisor.email, "pw")

    new_start = base + timedelta(hours=5)
    new_end = new_start + timedelta(minutes=30)
    resp = await client.patch(
        f"/api/v1/appointments/{appt_b_id}",
        json={"scheduled_start": new_start.isoformat(), "scheduled_end": new_end.isoformat()},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["scheduled_start"].startswith(new_start.isoformat()[:16])
