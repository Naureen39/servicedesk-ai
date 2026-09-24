"""Auth/RBAC dependencies shared by every protected router (Section 2.3).

`require_permission(...)` is the FastAPI dependency named explicitly in the plan. Location
scoping restricts `service_advisor` users to rows at their own `location_id`; every other role
sees all locations.
"""

from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.permissions import ROLE_SERVICE_ADVISOR
from app.core.security import decode_access_token, decode_anonymous_session_token
from app.db.base import get_db
from app.db.models.identity import User

_bearer = HTTPBearer(auto_error=False)


class CurrentUser:
    def __init__(
        self,
        id: str,
        email: str,
        roles: list[str],
        permissions: list[str],
        location_id: int | None,
        mfa_enabled: bool = False,
    ):
        self.id = id
        self.email = email
        self.roles = roles
        self.permissions = permissions
        self.location_id = location_id
        self.mfa_enabled = mfa_enabled

    def has_permission(self, code: str) -> bool:
        return code in self.permissions

    def has_role(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if credentials is None:
        raise AppError(401, "Missing bearer token", type_slug="https://meridian.example/problems/unauthenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise AppError(401, "Access token expired", type_slug="https://meridian.example/problems/token-expired") from None
    except jwt.InvalidTokenError:
        raise AppError(401, "Invalid access token", type_slug="https://meridian.example/problems/invalid-token") from None

    user_id = payload.get("sub")
    try:
        uuid.UUID(str(user_id))
    except ValueError:
        raise AppError(401, "Invalid access token", type_slug="https://meridian.example/problems/invalid-token") from None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppError(401, "User not found or inactive", type_slug="https://meridian.example/problems/unauthenticated")

    return CurrentUser(
        id=str(user.id),
        email=user.email,
        roles=payload.get("roles", []),
        permissions=payload.get("permissions", []),
        location_id=user.location_id,
        mfa_enabled=user.mfa_enabled,
    )


def require_permission(*codes: str):
    """FastAPI dependency: 403s unless the current user has at least one of `codes`."""

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(user.has_permission(c) for c in codes):
            raise AppError(
                403,
                f"Missing required permission: {' or '.join(codes)}",
                type_slug="https://meridian.example/problems/forbidden",
            )
        return user

    return _check


def require_role(*roles: str):
    """FastAPI dependency: 403s unless the current user has at least one of `roles`."""

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.has_role(*roles):
            raise AppError(
                403,
                f"Missing required role: {' or '.join(roles)}",
                type_slug="https://meridian.example/problems/forbidden",
            )
        return user

    return _check


def location_filter(user: CurrentUser, requested_location_id: int | None) -> int | None:
    """Enforces location scoping for `service_advisor` (Section 2.3): they may only query
    their own location, regardless of what was requested. Every other role passes through
    the caller's requested filter unchanged (None = all locations)."""
    if user.has_role(ROLE_SERVICE_ADVISOR):
        return user.location_id
    return requested_location_id


async def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def get_anonymous_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Validates the short-lived anonymous chat session token issued by POST /chat/session
    (Section 2.2). Public customers never authenticate as a `User`; this is their only
    credential, scoped to a single conversation_id."""
    if credentials is None:
        raise AppError(401, "Missing chat session token", type_slug="https://meridian.example/problems/unauthenticated")
    try:
        return decode_anonymous_session_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise AppError(401, "Chat session expired", type_slug="https://meridian.example/problems/token-expired") from None
    except jwt.InvalidTokenError:
        raise AppError(401, "Invalid chat session token", type_slug="https://meridian.example/problems/invalid-token") from None
