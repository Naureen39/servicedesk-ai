from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.base import async_session_factory

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _seed_vehicle_catalog():
    async with async_session_factory() as db:
        await db.execute(
            text(
                "INSERT INTO vehicle_catalog (year, make, model, nhtsa_model_name) VALUES "
                "(2022, 'Toyota', 'Camry', 'Camry'), (2023, 'Toyota', 'Corolla', 'Corolla') "
                "ON CONFLICT (year, make, model) DO NOTHING"
            )
        )
        await db.commit()
    yield
    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM vehicle_catalog WHERE make = 'Toyota'"))
        await db.commit()


async def test_vehicle_years_is_public_and_returns_real_catalog_data(client):
    resp = await client.get("/api/v1/vehicles/years")
    assert resp.status_code == 200
    assert 2022 in resp.json()
    assert 2023 in resp.json()


async def test_vehicle_makes_filters_by_year(client):
    resp = await client.get("/api/v1/vehicles/makes", params={"year": 2022})
    assert resp.status_code == 200
    assert resp.json() == ["Toyota"]


async def test_decode_vin_rejects_wrong_length(client):
    resp = await client.get("/api/v1/vehicles/decode/TOOSHORT")
    assert resp.status_code == 400
