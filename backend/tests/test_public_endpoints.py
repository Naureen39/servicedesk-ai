"""Phase 7: real public endpoints the website reads from -- locations, services, contact
ticket creation, and the live NHTSA make/model/recalls lookups used by the homepage's Recall
Quick Check and the /recalls page.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac


async def test_list_locations_returns_seeded_locations(client):
    resp = await client.get("/api/v1/locations")
    assert resp.status_code == 200
    locations = resp.json()
    assert len(locations) >= 1
    assert locations[0]["name"]
    assert "mon_open" in locations[0]


async def test_list_services_returns_seeded_catalog(client):
    resp = await client.get("/api/v1/services")
    assert resp.status_code == 200
    services = resp.json()
    assert len(services) >= 1
    codes = [s["code"] for s in services]
    assert "OIL-CONV" in codes


async def test_get_single_service_by_code(client):
    resp = await client.get("/api/v1/services/OIL-CONV")
    assert resp.status_code == 200
    assert resp.json()["code"] == "OIL-CONV"


async def test_get_unknown_service_404s(client):
    resp = await client.get("/api/v1/services/NOPE-999")
    assert resp.status_code == 404


async def test_contact_form_creates_a_ticket(client):
    resp = await client.post(
        "/api/v1/contact",
        json={
            "name": "Jordan Smith",
            "email": "jordan@example.com",
            "phone": "614-555-0142",
            "subject": "Question about my last visit",
            "message": "I have a question about the invoice from my last oil change.",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["message_id"].startswith("MSG-")
    assert body["status"] == "open"


async def test_contact_form_rejects_invalid_email(client):
    resp = await client.post(
        "/api/v1/contact",
        json={"name": "Jordan Smith", "email": "not-an-email", "subject": "Hi", "message": "Hello"},
    )
    assert resp.status_code == 422


@pytest.mark.live
async def test_live_nhtsa_makes_and_models_and_recalls(client):
    makes_resp = await client.get("/api/v1/nhtsa/makes", params={"year": 2020})
    assert makes_resp.status_code == 200
    makes = makes_resp.json()
    assert "TOYOTA" in makes

    models_resp = await client.get("/api/v1/nhtsa/models", params={"year": 2020, "make": "TOYOTA"})
    assert models_resp.status_code == 200
    assert len(models_resp.json()) > 0

    recalls_resp = await client.get("/api/v1/nhtsa/recalls", params={"year": 2020, "make": "Toyota", "model": "Camry"})
    assert recalls_resp.status_code == 200
    recalls = recalls_resp.json()
    assert isinstance(recalls, list)
    assert len(recalls) > 0
    assert recalls[0]["campaign_number"]
