"""Unit test for app.services.rbac.load_roles_and_permissions: loads a user's effective
roles and the union of permissions granted by those roles (Section 2.3)."""

from __future__ import annotations

import pytest

from app.db.base import async_session_factory
from app.services.rbac import load_roles_and_permissions

from .conftest import create_user

pytestmark = pytest.mark.asyncio


async def test_loads_role_names_and_union_of_permissions():
    user = await create_user("rbac-service-test@example.com", "correct-password-1", "service_manager")

    async with async_session_factory() as db:
        roles, permissions = await load_roles_and_permissions(db, user.id)

    assert roles == ["service_manager"]
    assert "kb:write" in permissions
    assert "analytics:read" in permissions
    assert permissions == sorted(permissions)


async def test_admin_has_every_permission():
    user = await create_user("rbac-service-admin@example.com", "correct-password-1", "admin")

    async with async_session_factory() as db:
        roles, permissions = await load_roles_and_permissions(db, user.id)

    assert roles == ["admin"]
    assert "users:manage" in permissions
    assert "settings:manage" in permissions
