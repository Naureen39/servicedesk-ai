"""Phase 4 DoD: 50 scripted multi-turn conversations covering booking, reschedule, recall,
warranty, complaint, safety, and out-of-scope, run against the real dialog manager, real
Postgres, and the real trained intent classifier -- plus the average-LLM-calls-per-turn budget
and the two provider-outage scenarios (Groq disabled -> Gemini takes over; both disabled ->
deterministic flows still complete and free-text questions still escalate).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models.assistant import Conversation
from app.services.dialog.manager import handle_turn
from app.services.dialog.result import TurnResult

from .fake_llm import both_disabled_router, groq_disabled_router, working_router

pytestmark = pytest.mark.asyncio


@dataclass
class ScriptedConversation:
    name: str
    category: str
    turns: list[str]
    check: Callable[[list[TurnResult], Conversation], None]
    router_factory: Callable[[], object | None] = lambda: None


async def run_conversation(script: ScriptedConversation) -> tuple[list[TurnResult], Conversation]:
    conversation_id = f"CONV-{uuid.uuid4().hex[:10].upper()}"
    router = script.router_factory()
    results: list[TurnResult] = []

    async with async_session_factory() as db:
        conv = Conversation(conversation_id=conversation_id, channel="chat", started_at=datetime.now(UTC), location_id=1)
        db.add(conv)
        await db.commit()

        for message in script.turns:
            result = await handle_turn(db, conv, message, router, channel="chat")
            results.append(result)

        refreshed = await db.execute(select(Conversation).where(Conversation.conversation_id == conversation_id))
        conv = refreshed.scalar_one()

    return results, conv


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def assert_contained(results: list[TurnResult], conv: Conversation) -> None:
    assert conv.escalated is not True, f"expected contained, got escalated: {[r.text for r in results]}"


def assert_escalated(reason: str | None = None):
    def _check(results: list[TurnResult], conv: Conversation) -> None:
        assert conv.escalated is True, f"expected escalation, conversation not escalated: {[r.text for r in results]}"
        if reason is not None:
            assert any(r.escalate_reason == reason for r in results), (
                f"expected escalate_reason={reason}, got {[r.escalate_reason for r in results]}"
            )
    return _check


def assert_booking_created(results: list[TurnResult], conv: Conversation) -> None:
    assert conv.resulting_appointment_id is not None, f"expected an appointment to be created: {[r.text for r in results]}"
    assert conv.escalated is not True


def assert_reschedule_completed(appointment_id: str | None):
    """Phase 5 changed reschedule from an always-escalate stub to a real flow: verify by
    reference + last-4, offer new slots, book one. A completed reschedule should not
    escalate at all."""

    def _check(results: list[TurnResult], conv: Conversation) -> None:
        assert conv.escalated is not True, (
            f"expected reschedule of {appointment_id} to complete without escalation: {[r.text for r in results]}"
        )

    return _check


# ---------------------------------------------------------------------------
# Script generators (50 total: 10 booking, 6 reschedule, 8 recall, 8 warranty,
# 5 complaint, 5 safety, 5 out-of-scope, 3 extras)
# ---------------------------------------------------------------------------

BOOKING_CASES = [
    ("an oil change", "2020 Toyota Camry", "next Tuesday", "Alicia Gomez", "614-555-0101"),
    ("a tire rotation", "2019 Honda Civic", "this Friday", "Marcus Reed", "614-555-0102"),
    ("brake pads", "2021 Ford F-150", "next Monday", "Priya Shah", "614-555-0103"),
    ("a 60k service", "2018 Toyota Corolla", "next Wednesday", "Tomas Lund", "614-555-0104"),
    ("an oil change", "2020 Toyota Camry", "tomorrow", "Keisha Brown", "614-555-0105"),
    ("a tire rotation", "2019 Honda Civic", "next Thursday", "Owen Clarke", "614-555-0106"),
    ("brake pads", "2021 Ford F-150", "next Friday", "Nadia Farouk", "614-555-0107"),
    ("a 60k service", "2018 Toyota Corolla", "next Tuesday", "Ravi Patel", "614-555-0108"),
    ("an oil change", "2019 Honda Civic", "next Monday", "Elena Cruz", "614-555-0109"),
    ("a tire rotation", "2020 Toyota Camry", "this Saturday", "Diego Ramos", "614-555-0110"),
]


def _booking_script(i: int, service_text: str, vehicle_text: str, date_text: str, name: str, phone: str) -> ScriptedConversation:
    return ScriptedConversation(
        name=f"booking_{i}",
        category="booking",
        turns=[
            f"I need to book {service_text}",
            vehicle_text,
            date_text,
            name,
            phone,
            "1",
        ],
        check=assert_booking_created,
        router_factory=lambda: None,  # booking is 0 LLM calls end to end
    )


BOOKING_SCRIPTS = [_booking_script(i, *case) for i, case in enumerate(BOOKING_CASES, start=1)]


RESCHEDULE_COUNT = 6


RECALL_CASES = [
    ("does my 2020 Toyota Camry have any recalls", None),
    ("is there a recall on my car", "2020 Toyota Camry"),
    ("any recalls for a 2019 Honda Civic", None),
    ("has my vehicle been recalled", "2019 Honda Civic"),
    ("I want to check recalls for my 2021 Ford F-150", None),
    ("are there open recalls on a 2018 Toyota Corolla", None),
    ("check recalls", "2020 Toyota Camry"),
    ("is my 2019 Honda Civic under any safety recall", None),
]


def _recall_script(i: int, first_message: str, followup_vehicle: str | None) -> ScriptedConversation:
    turns = [first_message] if followup_vehicle is None else [first_message, followup_vehicle]
    return ScriptedConversation(
        name=f"recall_{i}",
        category="recall",
        turns=turns,
        check=assert_contained,
        router_factory=lambda: None,  # recall summaries fall back to template with no router
    )


RECALL_SCRIPTS = [_recall_script(i, msg, veh) for i, (msg, veh) in enumerate(RECALL_CASES, start=1)]


WARRANTY_QUESTIONS = [
    "how long is my powertrain warranty",
    "does the warranty cover a transmission repair",
    "is a recall repair covered even if I'm out of warranty",
    "what does my bumper to bumper warranty include",
    "do I need to pay if my car is still under warranty",
    "what's not covered by the warranty",
    "how many miles does my warranty last",
    "is an oil change covered under warranty",
]


def _warranty_script(i: int, question: str) -> ScriptedConversation:
    return ScriptedConversation(
        name=f"warranty_{i}",
        category="warranty",
        turns=[question],
        check=assert_contained,
        router_factory=working_router,
    )


WARRANTY_SCRIPTS = [_warranty_script(i, q) for i, q in enumerate(WARRANTY_QUESTIONS, start=1)]


COMPLAINT_MESSAGES = [
    "I'm really unhappy with the service I received last week",
    "nobody called me back about my car and it's been days",
    "you charged me for work that was never done",
    "the technician was rude to me at the front desk",
    "this is the second time you've messed up my appointment",
]

SAFETY_MESSAGES = [
    "my brakes feel like they're not working at all",
    "I smell smoke coming from the engine right now",
    "my airbag light won't turn off and the car shakes",
    "the steering suddenly feels loose while driving",
    "my car stalled on the highway this morning",
]

OUT_OF_SCOPE_MESSAGES = [
    "what's the capital of France",
    "what's your favorite movie",
    "can you recommend a good restaurant nearby",
    "what time does the stock market open",
    "do you know any good jokes",
]


def _single_turn_script(i: int, category: str, message: str, check) -> ScriptedConversation:
    return ScriptedConversation(name=f"{category}_{i}", category=category, turns=[message], check=check)


COMPLAINT_SCRIPTS = [_single_turn_script(i, "complaint", m, assert_escalated("complaint")) for i, m in enumerate(COMPLAINT_MESSAGES, start=1)]
SAFETY_SCRIPTS = [_single_turn_script(i, "safety", m, assert_escalated("safety_concern")) for i, m in enumerate(SAFETY_MESSAGES, start=1)]
OUT_OF_SCOPE_SCRIPTS = [_single_turn_script(i, "out_of_scope", m, assert_contained) for i, m in enumerate(OUT_OF_SCOPE_MESSAGES, start=1)]

EXTRA_SCRIPTS = [
    ScriptedConversation("greeting_1", "extra", ["hi there"], assert_contained),
    ScriptedConversation("pricing_1", "extra", ["how much does an oil change cost"], assert_contained),
    ScriptedConversation("cancel_1", "extra", ["I need to cancel my appointment", "MRD-000000", "614-555-9999"], assert_contained),
]


async def _build_all_scripts() -> list[ScriptedConversation]:
    scripts = list(BOOKING_SCRIPTS)

    for i in range(1, RESCHEDULE_COUNT + 1):
        seed = ScriptedConversation(
            name="reschedule-seed", category="booking",
            turns=["I need to book a tire rotation", "2019 Honda Civic", "next Thursday", f"Reschedule Seed {i}", f"614-555-030{i}", "1"],
            check=assert_booking_created,
        )
        _, conv = await run_conversation(seed)
        async with async_session_factory() as db:
            from app.db.models.business import Appointment

            result = await db.execute(select(Appointment).where(Appointment.appointment_id == conv.resulting_appointment_id))
            appt = result.scalar_one()
        scripts.append(
            ScriptedConversation(
                name=f"reschedule_{i}",
                category="reschedule",
                turns=["I need to reschedule my appointment", appt.reference_code, f"614-555-030{i}", "1"],
                check=assert_reschedule_completed(conv.resulting_appointment_id),
            )
        )

    scripts += RECALL_SCRIPTS
    scripts += WARRANTY_SCRIPTS
    scripts += COMPLAINT_SCRIPTS
    scripts += SAFETY_SCRIPTS
    scripts += OUT_OF_SCOPE_SCRIPTS
    scripts += EXTRA_SCRIPTS
    return scripts


async def test_fifty_scripted_conversations_pass_and_stay_within_llm_budget():
    scripts = await _build_all_scripts()
    assert len(scripts) == 50, f"expected exactly 50 scripts, built {len(scripts)}"

    total_turns = 0
    total_llm_calls = 0
    failures: list[str] = []

    for script in scripts:
        try:
            results, conv = await run_conversation(script)
            script.check(results, conv)
        except AssertionError as exc:
            failures.append(f"{script.name} ({script.category}): {exc}")
            continue

        total_turns += len(results)
        total_llm_calls += sum(1 for r in results if r.llm_provider is not None)

    assert not failures, "Scripted conversation failures:\n" + "\n".join(failures)

    avg_llm_calls_per_turn = total_llm_calls / total_turns
    print(f"\nTotal turns: {total_turns}, LLM calls: {total_llm_calls}, avg/turn: {avg_llm_calls_per_turn:.3f}")
    assert avg_llm_calls_per_turn < 0.35, f"average LLM calls per turn {avg_llm_calls_per_turn:.3f} exceeds 0.35 budget"


async def test_groq_disabled_failover_completes_warranty_flow_through_gemini():
    # A question not used by any other script in this file, so a response_cache hit from an
    # earlier test can't mask whether Gemini actually served this one.
    script = ScriptedConversation(
        name="failover_warranty",
        category="warranty",
        turns=["will the dealership cover a failed alternator under my factory warranty"],
        check=assert_contained,
        router_factory=groq_disabled_router,
    )
    results, conv = await run_conversation(script)
    script.check(results, conv)
    assert results[-1].llm_provider == "gemini", f"expected Gemini to have served the answer, got {results[-1].llm_provider}"


async def test_both_providers_disabled_booking_still_completes():
    script = ScriptedConversation(
        name="outage_booking", category="booking",
        turns=["I need to book an oil change", "2020 Toyota Camry", "next Tuesday", "Outage Test", "614-555-0199", "1"],
        check=assert_booking_created,
        router_factory=both_disabled_router,
    )
    results, conv = await run_conversation(script)
    script.check(results, conv)


async def test_both_providers_disabled_recall_check_still_completes():
    script = ScriptedConversation(
        name="outage_recall", category="recall",
        turns=["does my 2020 Toyota Camry have any recalls"],
        check=assert_contained,
        router_factory=both_disabled_router,
    )
    results, conv = await run_conversation(script)
    script.check(results, conv)
    assert all(r.llm_provider is None for r in results), "expected zero LLM calls with both providers disabled"


async def test_both_providers_disabled_free_text_question_escalates():
    script = ScriptedConversation(
        name="outage_warranty_escalates", category="warranty",
        turns=["what exactly is included in the bumper to bumper warranty coverage period"],
        check=assert_escalated("llm_unavailable"),
        router_factory=both_disabled_router,
    )
    results, conv = await run_conversation(script)
    script.check(results, conv)
