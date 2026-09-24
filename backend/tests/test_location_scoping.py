"""Section 2.3: "Enforce location scoping (advisors see only their location)"."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.base import async_session_factory

from .conftest import create_user, login

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _seed_locations_and_appointments():
    async with async_session_factory() as db:
        await db.execute(
            text(
                "INSERT INTO locations (location_id, name, bay_count) VALUES "
                "(1, 'Riverside', 14), (2, 'Northgate', 12) "
                "ON CONFLICT (location_id) DO NOTHING"
            )
        )
        await db.execute(
            text(
                """
                INSERT INTO customers (customer_id, first_name, last_name, created_at)
                VALUES ('CUST-SCOPE-1', 'Scope', 'Test', now())
                ON CONFLICT (customer_id) DO NOTHING
                """
            )
        )
        await db.execute(
            text(
                """
                INSERT INTO vehicles (vehicle_id, customer_id, year, make, model)
                VALUES ('VEH-SCOPE-1', 'CUST-SCOPE-1', 2022, 'Toyota', 'Camry')
                ON CONFLICT (vehicle_id) DO NOTHING
                """
            )
        )
        await db.execute(
            text(
                """
                INSERT INTO appointments (appointment_id, customer_id, vehicle_id, location_id, scheduled_start, scheduled_end, status)
                VALUES
                    ('APT-SCOPE-1', 'CUST-SCOPE-1', 'VEH-SCOPE-1', 1, now(), now(), 'booked'),
                    ('APT-SCOPE-2', 'CUST-SCOPE-1', 'VEH-SCOPE-1', 2, now(), now(), 'booked')
                ON CONFLICT (appointment_id) DO NOTHING
                """
            )
        )
        await db.commit()
    yield
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM appointments WHERE appointment_id LIKE 'APT-SCOPE-%'"))
        await db.execute(text("DELETE FROM vehicles WHERE vehicle_id = 'VEH-SCOPE-1'"))
        await db.execute(text("DELETE FROM customers WHERE customer_id = 'CUST-SCOPE-1'"))
        await db.commit()


async def test_service_advisor_only_sees_their_own_location(client):
    await create_user("advisor-scope@example.com", "correct-password-1", "service_advisor", location_id=1)
    token = await login(client, "advisor-scope@example.com", "correct-password-1")

    resp = await client.get("/api/v1/appointments", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    location_ids = {row["location_id"] for row in resp.json()}
    assert location_ids <= {1}
    assert "APT-SCOPE-2" not in [row["appointment_id"] for row in resp.json()]


async def test_service_advisor_cannot_override_location_filter(client):
    await create_user("advisor-scope2@example.com", "correct-password-1", "service_advisor", location_id=1)
    token = await login(client, "advisor-scope2@example.com", "correct-password-1")

    resp = await client.get(
        "/api/v1/appointments", params={"location_id": 2}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert all(row["location_id"] == 1 for row in resp.json())


async def test_service_manager_sees_all_locations(client):
    await create_user("manager-scope@example.com", "correct-password-1", "service_manager")
    token = await login(client, "manager-scope@example.com", "correct-password-1")

    resp = await client.get("/api/v1/appointments", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    location_ids = {row["location_id"] for row in resp.json()}
    assert {1, 2}.issubset(location_ids)
