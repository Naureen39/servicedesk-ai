"""Proves every protected endpoint in Section 2.5 rejects roles that lack the permission it
requires (DoD: "RBAC tests prove every endpoint rejects unauthorized roles").

For each (method, path) this asserts three things:
  - no token at all -> 401
  - a role that Section 2.3 does NOT grant the needed permission -> 403
  - a role that Section 2.3 DOES grant the needed permission -> not 401/403 (may be 404/200/etc,
    since some routes need a real entity to exist; what matters for RBAC is that the
    permission check itself passed)
"""

from __future__ import annotations

import pytest

from .conftest import create_user, login

pytestmark = pytest.mark.asyncio

DUMMY_ID = "does-not-exist"

# (method, path, role_without_permission, role_with_permission)
ENDPOINT_MATRIX = [
    ("GET", "/api/v1/appointments", "analyst", "service_advisor"),
    ("PATCH", f"/api/v1/appointments/{DUMMY_ID}", "analyst", "service_advisor"),
    ("DELETE", f"/api/v1/appointments/{DUMMY_ID}", "analyst", "service_advisor"),
    ("GET", "/api/v1/conversations", "analyst", "service_advisor"),
    ("GET", f"/api/v1/conversations/{DUMMY_ID}", "analyst", "service_advisor"),
    ("GET", "/api/v1/escalations", "analyst", "service_advisor"),
    ("PATCH", f"/api/v1/escalations/{DUMMY_ID}", "analyst", "service_advisor"),
    ("POST", f"/api/v1/escalations/{DUMMY_ID}/reply", "analyst", "service_advisor"),
    ("GET", "/api/v1/analytics/overview", "service_advisor", "analyst"),
    ("GET", "/api/v1/analytics/revenue", "service_advisor", "analyst"),
    ("GET", "/api/v1/analytics/operations", "service_advisor", "analyst"),
    ("GET", "/api/v1/analytics/technicians", "service_advisor", "analyst"),
    ("GET", "/api/v1/analytics/assistant", "service_advisor", "analyst"),
    ("GET", "/api/v1/analytics/recalls", "service_advisor", "analyst"),
    ("GET", "/api/v1/analytics/export.csv", "service_advisor", "analyst"),
    ("GET", "/api/v1/admin/users", "service_manager", "admin"),
    ("POST", "/api/v1/admin/users", "service_manager", "admin"),
    ("PATCH", f"/api/v1/admin/users/{DUMMY_ID}", "service_manager", "admin"),
    ("GET", "/api/v1/admin/roles", "service_manager", "admin"),
    ("GET", "/api/v1/admin/settings", "service_manager", "admin"),
    ("GET", "/api/v1/admin/audit-logs", "service_manager", "admin"),
    ("GET", "/api/v1/admin/kb", "service_advisor", "service_manager"),
]


@pytest.mark.parametrize("method,path,denied_role,allowed_role", ENDPOINT_MATRIX)
async def test_endpoint_rejects_unauthenticated(client, method, path, denied_role, allowed_role):
    resp = await client.request(method, path, json={} if method in ("POST", "PATCH") else None)
    assert resp.status_code == 401, f"{method} {path} should 401 with no token, got {resp.status_code}"


@pytest.mark.parametrize("method,path,denied_role,allowed_role", ENDPOINT_MATRIX)
async def test_endpoint_rejects_role_without_permission(client, method, path, denied_role, allowed_role):
    email = f"denied-{denied_role}-{abs(hash((method, path)))}@example.com"
    await create_user(email, "correct-password-1", denied_role, location_id=1)
    token = await login(client, email, "correct-password-1")

    resp = await client.request(
        method,
        path,
        headers={"Authorization": f"Bearer {token}"},
        json={} if method in ("POST", "PATCH") else None,
    )
    assert resp.status_code == 403, (
        f"{method} {path} should 403 for role={denied_role} (lacks permission), got {resp.status_code}: {resp.text}"
    )


@pytest.mark.parametrize("method,path,denied_role,allowed_role", ENDPOINT_MATRIX)
async def test_endpoint_allows_role_with_permission(client, method, path, denied_role, allowed_role):
    email = f"allowed-{allowed_role}-{abs(hash((method, path)))}@example.com"
    await create_user(email, "correct-password-1", allowed_role, location_id=1)
    token = await login(client, email, "correct-password-1")

    resp = await client.request(
        method,
        path,
        headers={"Authorization": f"Bearer {token}"},
        json={} if method in ("POST", "PATCH") else None,
    )
    assert resp.status_code != 401 and resp.status_code != 403, (
        f"{method} {path} should not reject role={allowed_role} (has permission), got {resp.status_code}: {resp.text}"
    )
