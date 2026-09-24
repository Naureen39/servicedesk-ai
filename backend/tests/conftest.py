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
from app.db.models.assistant import Conversation, Escalation, Message
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
