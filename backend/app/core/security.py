"""Password hashing, JWT issuance/verification, TOTP MFA, and PII lookup hashing.

Refresh tokens are opaque random secrets (not JWTs): the server stores only a SHA-256 hash of
each token alongside a `family_id`, so a leaked database dump never yields usable tokens and a
reused (already-rotated) refresh token can be detected and used to revoke its whole family
(Section 2.2: "reuse detection revokes the whole token family").
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

_settings = get_settings()
_ph = PasswordHasher()


# --- Passwords ---------------------------------------------------------------


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def needs_rehash(password_hash: str) -> bool:
    return _ph.check_needs_rehash(password_hash)


# --- Access tokens (JWT) ------------------------------------------------------


def create_access_token(subject: str, roles: list[str], permissions: list[str]) -> tuple[str, str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=_settings.access_token_ttl_minutes)
    jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "roles": roles,
        "permissions": permissions,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "access",
    }
    token = jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)
    return token, jti, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload


# --- Anonymous chat session tokens (Section 2.2) ------------------------------


def create_anonymous_session_token(conversation_id: str) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=_settings.anonymous_session_ttl_minutes)
    payload = {
        "conversation_id": conversation_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": "anon_session",
    }
    token = jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)
    return token, expires_at


def decode_anonymous_session_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])
    if payload.get("type") != "anon_session":
        raise jwt.InvalidTokenError("not an anonymous session token")
    return payload


# --- Refresh tokens (opaque, DB-backed) --------------------------------------


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=_settings.refresh_token_ttl_days)


# --- TOTP MFA -----------------------------------------------------------------


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str, issuer: str = "Meridian Assist") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


# --- PII lookup hashing (Section 2.4) -----------------------------------------
# Customer phone/email are encrypted at rest via pgcrypto (pgp_sym_encrypt) in the database
# layer; this HMAC lets the application look up a customer by phone/email without decrypting
# every row. Uses a key derived from PII_ENCRYPTION_KEY, never the raw value.


def lookup_hash(value: str) -> str:
    key = _settings.pii_encryption_key.encode("utf-8")
    return hmac.new(key, value.strip().lower().encode("utf-8"), hashlib.sha256).hexdigest()
