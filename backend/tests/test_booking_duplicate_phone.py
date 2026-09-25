"""Regression test: phone numbers are not unique across customers (households share lines,
and Phase 1's synthetic generator has a narrow enough number range that collisions across
18,000 customers are actually guaranteed by the pigeonhole principle). The booking flow must
not assume `SELECT ... WHERE phone_hash = ...` returns at most one row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.core.security import lookup_hash
from app.db.base import async_session_factory
from app.db.models.assistant import Conversation
from app.services.dialog.manager import handle_turn

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def duplicate_phone_customers():
    phone = "614-555-0177"
    phash = lookup_hash(phone)
    ids = [f"CUST-DUPTEST-{i}" for i in range(2)]
    async with async_session_factory() as db:
        for cid in ids:
            await db.execute(
                text(
                    "INSERT INTO customers (customer_id, first_name, last_name, phone_hash, created_at) "
                    "VALUES (:cid, 'Dup', 'Test', :phash, now())"
                ),
                {"cid": cid, "phash": phash},
            )
        await db.commit()
    yield phone
    async with async_session_factory() as db:
        await db.execute(
            text(
                "UPDATE conversations SET resulting_appointment_id = NULL WHERE resulting_appointment_id IN "
                "(SELECT appointment_id FROM appointments WHERE customer_id IN "
                "(SELECT customer_id FROM customers WHERE phone_hash = :phash OR customer_id LIKE 'CUST-DUPTEST-%'))"
            ),
            {"phash": phash},
        )
        await db.execute(
            text(
                "DELETE FROM appointments WHERE customer_id IN "
                "(SELECT customer_id FROM customers WHERE phone_hash = :phash OR customer_id LIKE 'CUST-DUPTEST-%')"
            ),
            {"phash": phash},
        )
        await db.execute(
            text(
                "DELETE FROM vehicles WHERE customer_id IN "
                "(SELECT customer_id FROM customers WHERE phone_hash = :phash OR customer_id LIKE 'CUST-DUPTEST-%')"
            ),
            {"phash": phash},
        )
        await db.execute(text("DELETE FROM customers WHERE phone_hash = :phash OR customer_id LIKE 'CUST-DUPTEST-%'"), {"phash": phash})
        await db.commit()


async def test_booking_completes_when_phone_hash_matches_multiple_customers(duplicate_phone_customers):
    phone = duplicate_phone_customers
    conversation_id = f"CONV-{uuid.uuid4().hex[:10].upper()}"

    async with async_session_factory() as db:
        conv = Conversation(conversation_id=conversation_id, channel="chat", started_at=datetime.now(UTC), location_id=1)
        db.add(conv)
        await db.commit()

        for message in ["I need to book an oil change", "2020 Toyota Camry", "next Tuesday", "Dup Customer", phone, "1"]:
            result = await handle_turn(db, conv, message, None, channel="chat")

    assert result.contained is True
    assert conv.resulting_appointment_id is not None
