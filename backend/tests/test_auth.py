from __future__ import annotations

import pyotp
import pytest

from app.core.security import generate_totp_secret
from app.db.base import async_session_factory
from app.db.models.identity import MfaSecret

from .conftest import create_user, login

pytestmark = pytest.mark.asyncio


async def test_login_success_returns_access_token_and_refresh_cookie(client):
    await create_user("mgr@example.com", "correct-password-1", "service_manager")
    resp = await client.post("/api/v1/auth/login", json={"email": "mgr@example.com", "password": "correct-password-1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["mfa_required"] is False
    assert "refresh_token" in resp.cookies


async def test_login_wrong_password_returns_generic_error(client):
    await create_user("mgr2@example.com", "correct-password-1", "service_manager")
    resp = await client.post("/api/v1/auth/login", json={"email": "mgr2@example.com", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


async def test_login_unknown_email_returns_same_generic_error(client):
    resp = await client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


async def test_account_locks_after_five_failed_attempts(client):
    await create_user("locktest@example.com", "correct-password-1", "service_advisor")
    for _ in range(5):
        resp = await client.post("/api/v1/auth/login", json={"email": "locktest@example.com", "password": "wrong"})
        assert resp.status_code == 401

    # Even the correct password is now rejected with 423 while locked.
    resp = await client.post("/api/v1/auth/login", json={"email": "locktest@example.com", "password": "correct-password-1"})
    assert resp.status_code == 423


async def test_mfa_required_flow(client):
    user = await create_user("admin2@example.com", "correct-password-1", "admin", mfa=True)
    secret = generate_totp_secret()
    async with async_session_factory() as db:
        db.add(MfaSecret(user_id=user.id, secret=secret))
        await db.commit()

    resp = await client.post("/api/v1/auth/login", json={"email": "admin2@example.com", "password": "correct-password-1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["mfa_required"] is True
    assert body["access_token"] == ""
    challenge_token = body["mfa_challenge_token"]

    code = pyotp.TOTP(secret).now()
    resp2 = await client.post("/api/v1/auth/mfa/verify", json={"mfa_challenge_token": challenge_token, "code": code})
    assert resp2.status_code == 200
    assert resp2.json()["access_token"]


async def test_mfa_verify_rejects_wrong_code(client):
    user = await create_user("admin3@example.com", "correct-password-1", "admin", mfa=True)
    secret = generate_totp_secret()
    async with async_session_factory() as db:
        db.add(MfaSecret(user_id=user.id, secret=secret))
        await db.commit()

    resp = await client.post("/api/v1/auth/login", json={"email": "admin3@example.com", "password": "correct-password-1"})
    challenge_token = resp.json()["mfa_challenge_token"]

    resp2 = await client.post("/api/v1/auth/mfa/verify", json={"mfa_challenge_token": challenge_token, "code": "000000"})
    assert resp2.status_code == 401


async def test_me_requires_bearer_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_returns_roles_and_permissions(client):
    await create_user("mgr3@example.com", "correct-password-1", "service_manager")
    token = await login(client, "mgr3@example.com", "correct-password-1")
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["roles"] == ["service_manager"]
    assert "escalations:write" in body["permissions"]


async def test_refresh_rotates_token_and_old_cookie_is_rejected(client):
    await create_user("rot@example.com", "correct-password-1", "service_manager")
    await client.post("/api/v1/auth/login", json={"email": "rot@example.com", "password": "correct-password-1"})

    resp1 = await client.post("/api/v1/auth/refresh")
    assert resp1.status_code == 200
    new_access_1 = resp1.json()["access_token"]

    resp2 = await client.post("/api/v1/auth/refresh")
    assert resp2.status_code == 200
    new_access_2 = resp2.json()["access_token"]
    assert new_access_1 != new_access_2


async def test_refresh_reuse_detection_revokes_family(client):
    await create_user("reuse@example.com", "correct-password-1", "service_manager")
    login_resp = await client.post("/api/v1/auth/login", json={"email": "reuse@example.com", "password": "correct-password-1"})
    old_cookie = login_resp.cookies.get("refresh_token")

    # Rotate once (this revokes `old_cookie` server-side and issues a new one).
    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200
    new_cookie = refresh_resp.cookies.get("refresh_token")
    assert new_cookie != old_cookie

    # Replay the old (already-rotated) refresh token: must be detected and rejected.
    client.cookies.set("refresh_token", old_cookie)
    reuse_resp = await client.post("/api/v1/auth/refresh")
    assert reuse_resp.status_code == 401
    assert reuse_resp.json()["type"] == "https://meridian.example/problems/token-reuse-detected"

    # The token issued by the rotation just before the replay must ALSO now be revoked,
    # because reuse detection revokes the whole family, not just the replayed token.
    client.cookies.set("refresh_token", new_cookie)
    after_reuse_resp = await client.post("/api/v1/auth/refresh")
    assert after_reuse_resp.status_code == 401


async def test_refresh_without_cookie_is_unauthenticated(client):
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_logout_revokes_refresh_token(client):
    await create_user("out@example.com", "correct-password-1", "service_manager")
    await client.post("/api/v1/auth/login", json={"email": "out@example.com", "password": "correct-password-1"})

    logout_resp = await client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204

    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 401
