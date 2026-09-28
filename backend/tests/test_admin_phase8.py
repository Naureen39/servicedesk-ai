"""Phase 8 Admin: persisted runtime settings (real read/write, live effect on the dialog
manager and LLM router) and the knowledge base editor (real markdown file, real re-embedding).

Regression test included: the settings PATCH endpoint used to 500 because
`Decimal('0.550')` (from the Numeric(4,3) column) isn't JSON-serializable when written to the
audit log's `before` snapshot -- caught by actually exercising the PATCH, not just checking the
response shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import delete, select

from app.db.base import async_session_factory
from app.db.models.identity import AppSettings
from app.db.models.knowledge import KbChunk, KbDocument
from app.services import settings_store
from app.services.llm.router import LLMRouter

from .conftest import create_user, login

pytestmark = pytest.mark.asyncio

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
async def _reset_settings_after():
    yield
    async with async_session_factory() as db:
        row = (await db.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one()
        row.confidence_threshold = 0.55
        row.llm_primary = "groq"
        await db.commit()
        await settings_store.refresh(db)


async def test_settings_patch_persists_and_takes_immediate_effect(client, auth_headers):
    admin = await create_user("admin-settings@example.com", "pw", "admin", mfa=False)
    token = await login(client, admin.email, "pw")

    resp = await client.patch("/api/v1/admin/settings", json={"confidence_threshold": 0.61}, headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["confidence_threshold"] == pytest.approx(0.61)

    # Persisted in the DB, not just returned.
    async with async_session_factory() as db:
        row = (await db.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one()
        assert float(row.confidence_threshold) == pytest.approx(0.61)

    # Live in the in-process cache the dialog manager reads, with no restart.
    assert settings_store.confidence_threshold() == pytest.approx(0.61)


async def test_router_order_reflects_live_settings_without_reconstruction():
    router = LLMRouter({"groq": object(), "gemini": object()})
    async with async_session_factory() as db:
        row = (await db.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one()
        row.llm_primary = "gemini"
        await db.commit()
        await settings_store.refresh(db)
    assert router.order[0] == "gemini"

    async with async_session_factory() as db:
        row = (await db.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one()
        row.llm_primary = "groq"
        await db.commit()
        await settings_store.refresh(db)
    assert router.order[0] == "groq"


async def test_non_admin_cannot_write_settings(client, auth_headers):
    manager = await create_user("manager-settings@example.com", "pw", "service_manager", mfa=False)
    token = await login(client, manager.email, "pw")
    resp = await client.patch("/api/v1/admin/settings", json={"confidence_threshold": 0.5}, headers=auth_headers(token))
    assert resp.status_code == 403


async def test_kb_create_update_publish_round_trip(client, auth_headers):
    manager = await create_user("manager-kb@example.com", "pw", "service_manager", mfa=False)
    token = await login(client, manager.email, "pw")
    headers = auth_headers(token)

    # This endpoint writes a real file to dataset/reference/knowledge_base/, outside any DB
    # transaction the test framework can roll back -- if an assertion below failed before the
    # unlink ran, the stray file would make every future run of this test fail with a 409
    # "already exists" conflict, so the cleanup must run even when the test fails partway.
    doc_path = REPO_ROOT / "dataset" / "reference" / "knowledge_base" / "test-phase8-doc.md"
    try:
        create_resp = await client.post(
            "/api/v1/admin/kb",
            json={"source_path": "test-phase8-doc.md", "title": "Test Phase 8 Doc", "content": "# Test Phase 8 Doc\n\nSome real content about oil changes."},
            headers=headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        doc = create_resp.json()
        assert doc["content"].startswith("# Test Phase 8 Doc")
        doc_id = doc["id"]

        get_resp = await client.get(f"/api/v1/admin/kb/{doc_id}", headers=headers)
        assert get_resp.status_code == 200
        assert "oil changes" in get_resp.json()["content"]

        update_resp = await client.put(
            f"/api/v1/admin/kb/{doc_id}",
            json={"content": "# Test Phase 8 Doc\n\nUpdated content about tire rotations."},
            headers=headers,
        )
        assert update_resp.status_code == 200
        assert "tire rotations" in update_resp.json()["content"]

        publish_resp = await client.post(f"/api/v1/admin/kb/{doc_id}/publish", headers=headers)
        assert publish_resp.status_code == 200, publish_resp.text
        result = publish_resp.json()
        assert result["unchanged"] is False
        assert result["chunk_count"] >= 1

        # Publishing again with no further edit should be a real no-op (content hash unchanged).
        republish_resp = await client.post(f"/api/v1/admin/kb/{doc_id}/publish", headers=headers)
        assert republish_resp.json()["unchanged"] is True
    finally:
        # Delete by source_path, not just the id captured above -- if the endpoint call itself
        # never returned (e.g. the process was killed mid-test), doc_id was never bound, so
        # cleanup must be able to find and remove the row without it.
        doc_path.unlink(missing_ok=True)
        async with async_session_factory() as cleanup_db:
            await cleanup_db.execute(delete(KbChunk).where(KbChunk.source_path.like("%test-phase8-doc.md")))
            await cleanup_db.execute(delete(KbDocument).where(KbDocument.source_path.like("%test-phase8-doc.md")))
            await cleanup_db.commit()
