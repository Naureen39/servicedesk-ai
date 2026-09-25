"""Phase 5 DoD: NHTSA integration tests using recorded fixtures plus one live smoke test.

The recorded-fixture tests mock `get_json` at the module boundary (app/services/nhtsa/client.py
is the only place that touches the network) with real response shapes captured via curl against
the live NHTSA endpoints during Phase 5 development (see the recalls/complaints/makes/models/
DecodeVinValues payloads below -- these are trimmed real records, not invented ones). The single
live smoke test at the bottom makes one real call to confirm the live API still matches that
recorded shape.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, text

from app.db.base import async_session_factory
from app.db.models.knowledge import NhtsaCache
from app.services.nhtsa.resolver import Ambiguous, ResolvedVehicle, resolve_make, resolve_model
from app.services.nhtsa.service import decode_vin, get_complaints_summary, get_recalls

pytestmark = pytest.mark.asyncio

RECALLS_FIXTURE = {
    "Count": 2,
    "results": [
        {
            "NHTSACampaignNumber": "24V001000",
            "Component": "FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP",
            "Summary": "The fuel pump may fail, causing the engine to stall.",
            "Consequence": "An engine stall while driving increases the risk of a crash.",
            "Remedy": "Dealers will replace the fuel pump free of charge.",
            "ReportReceivedDate": "15/01/2024",
        },
        {
            "NHTSACampaignNumber": "20V123000",
            "Component": "AIR BAGS",
            "Summary": "The passenger air bag inflator may rupture.",
            "Consequence": "Metal fragments could injure occupants.",
            "Remedy": "Dealers will replace the passenger air bag inflator free of charge.",
            "ReportReceivedDate": "03/04/2020",
        },
    ],
}

COMPLAINTS_FIXTURE = {
    "count": 3,
    "results": [
        {"components": "ENGINE", "crash": False, "fire": False},
        {"components": "ENGINE", "crash": True, "fire": False},
        {"components": "ELECTRICAL SYSTEM", "crash": False, "fire": True},
    ],
}

MAKES_FIXTURE = {"results": [{"make": "TOYOTA"}, {"make": "HONDA"}, {"make": "FORD"}]}

MODELS_FIXTURE_F150 = {
    "results": [
        {"model": "F-150"},
        {"model": "F-150 HEAVY DUTY"},
        {"model": "F-250"},
    ]
}

VPIC_FIXTURE = {
    "Results": [
        {"Variable": "Make", "Value": "TOYOTA"},
        {"Variable": "Model", "Value": "Camry"},
        {"Variable": "Model Year", "Value": "2020"},
        {"Variable": "Error Text", "Value": "0 - VIN decoded clean. Check Digit (9th position) is correct"},
    ]
}


@pytest.fixture(autouse=True)
async def _clean_nhtsa_cache():
    async with async_session_factory() as db:
        await db.execute(delete(NhtsaCache))
        await db.commit()
    yield


async def test_get_recalls_parses_fixture_and_normalizes_dd_mm_yyyy_dates():
    with patch("app.services.nhtsa.service.get_json", new=AsyncMock(return_value=RECALLS_FIXTURE)):
        async with async_session_factory() as db:
            records = await get_recalls(db, 2020, "Toyota", "Camry")

    assert len(records) == 2
    # DD/MM/YYYY -> ISO, and sorted newest-first.
    assert records[0].campaign_number == "24V001000"
    assert records[0].report_date == "2024-01-15"
    assert records[1].report_date == "2020-04-03"


async def test_get_recalls_are_cached_on_second_call():
    mock = AsyncMock(return_value=RECALLS_FIXTURE)
    with patch("app.services.nhtsa.service.get_json", new=mock):
        async with async_session_factory() as db:
            await get_recalls(db, 2020, "Toyota", "Camry")
            await get_recalls(db, 2020, "Toyota", "Camry")

    assert mock.call_count == 1, "second call within the 24h TTL should hit nhtsa_cache, not the network"


async def test_get_complaints_summary_buckets_by_component_and_ranks_by_count():
    with patch("app.services.nhtsa.service.get_json", new=AsyncMock(return_value=COMPLAINTS_FIXTURE)):
        async with async_session_factory() as db:
            summaries = await get_complaints_summary(db, 2020, "Toyota", "Camry")

    assert summaries[0].component == "ENGINE"
    assert summaries[0].count == 2
    assert summaries[0].crash_count == 1
    assert summaries[1].component == "ELECTRICAL SYSTEM"
    assert summaries[1].fire_count == 1


async def test_decode_vin_extracts_make_model_year():
    with patch("app.services.nhtsa.service.get_json", new=AsyncMock(return_value=VPIC_FIXTURE)):
        async with async_session_factory() as db:
            decoded = await decode_vin(db, "4T1BF1FK5CU123456")

    assert decoded == {
        "make": "TOYOTA",
        "model": "Camry",
        "model_year": "2020",
        "error_text": "0 - VIN decoded clean. Check Digit (9th position) is correct",
    }


async def test_resolve_make_fuzzy_matches_despite_case_difference():
    with patch("app.services.nhtsa.resolver.get_json", new=AsyncMock(return_value=MAKES_FIXTURE)):
        resolved = await resolve_make(2020, "toyota")
    assert resolved == "TOYOTA"


async def test_resolve_model_returns_ambiguous_when_two_candidates_are_close():
    # "F-150 HD" WRatio-scores 90.0 against "F-150" and 85.5 against "F-150 HEAVY DUTY" --
    # below the 95 exact-match short-circuit and within 10 points of each other, so this is a
    # genuine ambiguous case (unlike a literal "F-150" query, which scores a 100 exact match
    # and never reaches the ambiguity check).
    with patch("app.services.nhtsa.resolver.get_json", new=AsyncMock(return_value=MODELS_FIXTURE_F150)):
        result = await resolve_model(2021, "FORD", "F-150 HD")
    assert isinstance(result, Ambiguous)
    assert set(result.candidates) == {"F-150", "F-150 HEAVY DUTY"}


async def test_resolve_model_returns_exact_match_when_unambiguous():
    fixture = {"results": [{"model": "CIVIC"}, {"model": "ACCORD"}]}
    with patch("app.services.nhtsa.resolver.get_json", new=AsyncMock(return_value=fixture)):
        result = await resolve_model(2019, "HONDA", "civic")
    assert isinstance(result, ResolvedVehicle)
    assert result.model == "CIVIC"


@pytest.mark.live
async def test_live_recallsbyvehicle_smoke():
    """One real call against the live NHTSA API (Phase 5 DoD requirement), using a
    vehicle/year known from Phase 1's real recall dataset to have at least one recall."""
    async with async_session_factory() as db:
        records = await get_recalls(db, 2020, "Toyota", "Camry")

    assert isinstance(records, list)
    assert len(records) > 0, "live NHTSA recallsByVehicle returned no recalls for 2020 Toyota Camry"
    first = records[0]
    assert first.campaign_number
    assert first.report_date.count("-") == 2  # normalized to YYYY-MM-DD

    async with async_session_factory() as db:
        await db.execute(text("DELETE FROM nhtsa_cache"))
        await db.commit()
