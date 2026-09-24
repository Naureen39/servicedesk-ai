from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.base import async_session_factory
from app.services.pii import redact_pii, rehydrate


def test_redact_pii_masks_phone_email_and_vin_but_keeps_vin_suffix():
    text_in = "Call me at 614-555-0123 or email jane@example.com about VIN 1HGCM82633A004352"
    redacted, mapping = redact_pii(text_in)

    assert "614-555-0123" not in redacted
    assert "jane@example.com" not in redacted
    assert "1HGCM82633A004352" not in redacted
    assert redacted.endswith("004352")  # last 6 characters of the VIN are kept, per Section 2.4
    # Phone and email are fully restorable placeholders; the truncated VIN is intentionally
    # final (never rehydrated back to the full VIN).
    rehydrated = rehydrate(redacted, mapping)
    assert "614-555-0123" in rehydrated
    assert "jane@example.com" in rehydrated
    assert rehydrated.endswith("004352")


def test_redact_pii_handles_text_with_no_pii():
    text_in = "What are your hours on Saturday?"
    redacted, mapping = redact_pii(text_in)
    assert redacted == text_in
    assert mapping == {}


@pytest.mark.asyncio
async def test_customer_phone_and_email_are_encrypted_at_rest_via_pgcrypto():
    async with async_session_factory() as db:
        await db.execute(
            text(
                """
                INSERT INTO customers (customer_id, first_name, last_name, phone_encrypted, email_encrypted, phone_hash, email_hash, created_at)
                VALUES (:cid, 'Test', 'Customer', pgp_sym_encrypt(:phone, :key), pgp_sym_encrypt(:email, :key), :phash, :ehash, now())
                """
            ),
            {
                "cid": "CUST-TEST-001",
                "phone": "614-555-9999",
                "email": "test.customer@example.com",
                "key": "test-pii-key",
                "phash": "irrelevant-for-this-test",
                "ehash": "irrelevant-for-this-test",
            },
        )
        await db.commit()

        raw = await db.execute(
            text("SELECT phone_encrypted, email_encrypted FROM customers WHERE customer_id = 'CUST-TEST-001'")
        )
        phone_bytes, email_bytes = raw.one()
        assert phone_bytes is not None
        # The ciphertext must not contain the plaintext anywhere.
        assert b"614-555-9999" not in phone_bytes
        assert b"test.customer" not in email_bytes

        decrypted = await db.execute(
            text(
                "SELECT pgp_sym_decrypt(phone_encrypted, :key), pgp_sym_decrypt(email_encrypted, :key) "
                "FROM customers WHERE customer_id = 'CUST-TEST-001'"
            ),
            {"key": "test-pii-key"},
        )
        phone, email = decrypted.one()
        assert phone == "614-555-9999"
        assert email == "test.customer@example.com"

        await db.execute(text("DELETE FROM customers WHERE customer_id = 'CUST-TEST-001'"))
        await db.commit()
