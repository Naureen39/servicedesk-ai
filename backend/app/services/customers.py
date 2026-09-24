"""Customer phone/email column encryption via pgcrypto (Section 2.4).

Encryption and decryption happen inside PostgreSQL (`pgp_sym_encrypt`/`pgp_sym_decrypt`) so the
plaintext key material only ever needs to reach the database connection, never application
memory beyond the query text. `lookup_hash` (HMAC-SHA256, app/core/security.py) lets the
application find a customer by phone or email without decrypting every row.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import lookup_hash

_settings = get_settings()


async def encrypt_value(db: AsyncSession, plaintext: str | None) -> bytes | None:
    if plaintext is None or plaintext == "":
        return None
    result = await db.execute(
        text("SELECT pgp_sym_encrypt(:val, :key)"),
        {"val": plaintext, "key": _settings.pii_encryption_key},
    )
    return result.scalar_one()


async def decrypt_value(db: AsyncSession, ciphertext: bytes | None) -> str | None:
    if ciphertext is None:
        return None
    result = await db.execute(
        text("SELECT pgp_sym_decrypt(:val, :key)"),
        {"val": ciphertext, "key": _settings.pii_encryption_key},
    )
    return result.scalar_one()


async def find_customer_id_by_phone(db: AsyncSession, phone: str) -> str | None:
    result = await db.execute(
        text("SELECT customer_id FROM customers WHERE phone_hash = :h LIMIT 1"),
        {"h": lookup_hash(phone)},
    )
    return result.scalar_one_or_none()
