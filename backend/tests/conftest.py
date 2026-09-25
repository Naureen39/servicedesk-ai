from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:55432/meridian_test")
os.environ.setdefault("JWT_SECRET", "test-access-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-secret")
os.environ.setdefault("PII_ENCRYPTION_KEY", "test-pii-key")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core.security import hash_password
from app.db.base import async_session_factory
from app.db.models.assistant import Conversation, Escalation, Message, ResponseCache
from app.db.models.identity import AuditLog, MfaSecret, RefreshToken, User
from app.main import app

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "scripts"))
from seed import seed_permissions, seed_roles


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _seed_rbac():
    async with async_session_factory() as db:
        permissions = await seed_permissions(db)
        await seed_roles(db, permissions)
        await db.commit()


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _seed_dialog_reference_data(_seed_rbac):
    """Seeds the reference data the Phase 4 dialog manager reads: real locations/technicians/
    service_catalog rows from dataset/reference/, a small curated vehicle_catalog and
    recall_campaigns set for the scripted conversations, and real embedded kb_chunks (via the
    actual embed_kb.py, run once against this test database)."""
    import subprocess

    import pandas as pd
    from sqlalchemy import text

    from app.services.nlu import catalog_cache

    async with async_session_factory() as db:
        for name, cols in [
            ("locations", ["location_id", "name", "address", "city", "state", "zip", "latitude", "longitude",
                            "timezone", "bay_count", "phone", "mon_open", "mon_close", "tue_open", "tue_close",
                            "wed_open", "wed_close", "thu_open", "thu_close", "fri_open", "fri_close",
                            "sat_open", "sat_close", "sun_open", "sun_close"]),
            ("technicians", ["technician_id", "name", "location_id", "skill_level", "certifications",
                              "shift_pattern", "hire_date", "efficiency_base"]),
            ("service_catalog", ["code", "name", "category", "labor_hours_min", "labor_hours_max",
                                  "parts_cost_min", "parts_cost_max", "duration_min", "bay_type", "skill_level"]),
        ]:
            df = pd.read_csv(REPO_ROOT / "dataset" / "reference" / f"{name}.csv", dtype={"zip": str})
            if "hire_date" in df.columns:
                df["hire_date"] = pd.to_datetime(df["hire_date"]).dt.date
            df = df.astype(object).where(df.notna(), None)
            col_list = ", ".join(cols)
            placeholders = ", ".join(f":{c}" for c in cols)
            for row in df.to_dict("records"):
                await db.execute(
                    text(f"INSERT INTO {name} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"), row
                )

        vehicles = [
            (2020, "Toyota", "Camry", "Camry"),
            (2019, "Honda", "Civic", "Civic"),
            (2021, "Ford", "F-150", "F-150"),
            (2018, "Toyota", "Corolla", "Corolla"),
        ]
        for year, make, model, nhtsa_name in vehicles:
            await db.execute(
                text(
                    "INSERT INTO vehicle_catalog (year, make, model, nhtsa_model_name) "
                    "VALUES (:year, :make, :model, :nhtsa_name) ON CONFLICT DO NOTHING"
                ),
                {"year": year, "make": make, "model": model, "nhtsa_name": nhtsa_name},
            )

        await db.execute(
            text(
                """
                INSERT INTO recall_campaigns
                    (campaign_number, make, model, model_year, component, summary, consequence, remedy, report_date)
                VALUES
                    ('24V001000', 'TOYOTA', 'Camry', 2020, 'FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP',
                     'The fuel pump may fail, causing the engine to stall.',
                     'An engine stall while driving increases the risk of a crash.',
                     'Dealers will replace the fuel pump free of charge.', '2024-01-15')
                ON CONFLICT DO NOTHING
                """
            )
        )
        await db.commit()

    for script in ["embed_kb.py", "build_scheduling_reference.py"]:
        result = subprocess.run(
            [str(REPO_ROOT / ".venv" / "Scripts" / "python.exe"), str(REPO_ROOT / "dataset" / "scripts" / script)],
            cwd=str(REPO_ROOT / "dataset" / "scripts"),
            env={**os.environ, "DATABASE_URL": "postgresql://postgres:postgres@localhost:55432/meridian_test"},
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, f"{script} failed:\n{result.stdout}\n{result.stderr}"

    async with async_session_factory() as db:
        await catalog_cache.refresh(db)

    from app.services import settings_store

    async with async_session_factory() as db:
        await settings_store.refresh(db)


@pytest_asyncio.fixture(autouse=True)
async def _clean_mutable_tables():
    """Runs before each test so auth/RBAC state (users, tokens, audit log) never leaks
    between tests, while the session-scoped roles/permissions seeded above stay in place.
    Also resets the slowapi rate limiter, since every ASGITransport request shares one fake
    client address -- without this, the login tests alone would blow through the real
    10/minute login limit partway through the suite."""
    from app.core.rate_limit import limiter

    limiter.reset()
    async with async_session_factory() as db:
        await db.execute(delete(Escalation))
        await db.execute(delete(Message))
        await db.execute(delete(Conversation))
        await db.execute(delete(ResponseCache))
        await db.execute(delete(AuditLog))
        await db.execute(delete(RefreshToken))
        await db.execute(delete(MfaSecret))
        await db.execute(delete(User))
        await db.commit()
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    # https:// base_url (not http://) so httpx's cookie jar will actually replay the
    # refresh_token cookie, which is marked Secure (Section 2.2).
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac


async def create_user(email: str, password: str, role_name: str, *, location_id: int | None = None, mfa: bool = False) -> User:
    from sqlalchemy import select

    from app.db.models.identity import Role

    async with async_session_factory() as db:
        result = await db.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one()
        user = User(
            email=email,
            password_hash=hash_password(password),
            location_id=location_id,
            roles=[role],
            mfa_enabled=mfa,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers():
    def _make(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    return _make
