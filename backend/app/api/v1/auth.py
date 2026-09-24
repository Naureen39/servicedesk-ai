"""Auth endpoints (Section 2.5): login, refresh, logout, MFA verify, me, and the anonymous
chat session token issuer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    refresh_token_expiry,
    verify_password,
    verify_totp,
)
from app.db.base import get_db
from app.db.models.identity import MfaSecret, RefreshToken, User
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse, MfaVerifyRequest, RefreshResponse
from app.services.rbac import load_roles_and_permissions

from .deps import CurrentUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

REFRESH_COOKIE_NAME = "refresh_token"
MFA_CHALLENGE_TTL_MINUTES = 5


def _generic_auth_error() -> AppError:
    # Section 2.2: "generic error messages" so failed-login responses do not reveal whether
    # the account exists.
    return AppError(401, "Invalid email or password", type_slug="https://meridian.example/problems/invalid-credentials")


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        path="/api/v1/auth",
    )


async def _issue_tokens(db: AsyncSession, response: Response, user: User) -> LoginResponse:
    roles, permissions = await load_roles_and_permissions(db, user.id)
    access_token, _, expires_at = create_access_token(str(user.id), roles, permissions)

    family_id = uuid.uuid4()
    raw_refresh = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=refresh_token_expiry(),
        )
    )
    await db.commit()

    _set_refresh_cookie(response, raw_refresh)
    ttl = int((expires_at - datetime.now(UTC)).total_seconds())
    return LoginResponse(access_token=access_token, expires_in=ttl)


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    if user is None:
        raise _generic_auth_error()

    now = datetime.now(UTC)
    if user.locked_until and user.locked_until > now:
        raise AppError(
            423,
            "Account temporarily locked due to repeated failed login attempts. Try again later.",
            type_slug="https://meridian.example/problems/account-locked",
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.account_lockout_threshold:
            user.locked_until = now + timedelta(minutes=settings.account_lockout_minutes)
        await db.commit()
        raise _generic_auth_error()

    if not user.is_active:
        raise _generic_auth_error()

    user.failed_login_attempts = 0
    user.locked_until = None

    if user.mfa_enabled:
        challenge_payload = {
            "sub": str(user.id),
            "type": "mfa_challenge",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=MFA_CHALLENGE_TTL_MINUTES)).timestamp()),
        }
        challenge_token = jwt.encode(challenge_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        await db.commit()
        return LoginResponse(access_token="", expires_in=0, mfa_required=True, mfa_challenge_token=challenge_token)

    await db.commit()
    return await _issue_tokens(db, response, user)


@router.post("/mfa/verify", response_model=LoginResponse)
@limiter.limit("10/minute")
async def mfa_verify(
    request: Request,
    response: Response,
    payload: MfaVerifyRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    try:
        claims = jwt.decode(payload.mfa_challenge_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError:
        raise AppError(401, "Invalid or expired MFA challenge", type_slug="https://meridian.example/problems/invalid-token") from None
    if claims.get("type") != "mfa_challenge":
        raise AppError(401, "Invalid MFA challenge token", type_slug="https://meridian.example/problems/invalid-token")

    user_id = claims["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _generic_auth_error()

    mfa_result = await db.execute(select(MfaSecret).where(MfaSecret.user_id == user.id))
    mfa_secret = mfa_result.scalar_one_or_none()
    if mfa_secret is None or not verify_totp(mfa_secret.secret, payload.code):
        raise AppError(401, "Invalid MFA code", type_slug="https://meridian.example/problems/invalid-mfa-code")

    return await _issue_tokens(db, response, user)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> RefreshResponse:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_token:
        raise AppError(401, "Missing refresh token", type_slug="https://meridian.example/problems/unauthenticated")

    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    stored = result.scalar_one_or_none()

    if stored is None:
        raise AppError(401, "Invalid refresh token", type_slug="https://meridian.example/problems/invalid-token")

    now = datetime.now(UTC)

    if stored.revoked_at is not None:
        # Reuse of an already-rotated (or already-logged-out) token: revoke the whole family.
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == stored.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.commit()
        raise AppError(
            401,
            "Refresh token reuse detected; all sessions for this device family have been revoked",
            type_slug="https://meridian.example/problems/token-reuse-detected",
        )

    if stored.expires_at < now:
        raise AppError(401, "Refresh token expired", type_slug="https://meridian.example/problems/token-expired")

    result = await db.execute(select(User).where(User.id == stored.user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppError(401, "User not found or inactive", type_slug="https://meridian.example/problems/unauthenticated")

    # Rotate: issue a new token in the same family, revoke the old one, link them.
    new_raw = new_refresh_token()
    new_row = RefreshToken(
        user_id=user.id,
        family_id=stored.family_id,
        token_hash=hash_refresh_token(new_raw),
        expires_at=refresh_token_expiry(),
    )
    db.add(new_row)
    await db.flush()

    stored.revoked_at = now
    stored.replaced_by_id = new_row.id
    await db.commit()

    _set_refresh_cookie(response, new_raw)

    roles, permissions = await load_roles_and_permissions(db, user.id)
    access_token, _, expires_at = create_access_token(str(user.id), roles, permissions)
    ttl = int((expires_at - now).total_seconds())
    return RefreshResponse(access_token=access_token, expires_in=ttl)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> None:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_token:
        token_hash = hash_refresh_token(raw_token)
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        stored = result.scalar_one_or_none()
        if stored is not None and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)
            await db.commit()
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")


@router.get("/me", response_model=MeResponse)
async def me(current_user: CurrentUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=None,
        roles=current_user.roles,
        permissions=current_user.permissions,
        mfa_enabled=current_user.mfa_enabled,
        location_id=current_user.location_id,
    )
