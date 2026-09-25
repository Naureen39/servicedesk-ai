"""Per-intent flow handlers (Section 4.2). Every handler here is deterministic (zero LLM
tokens) except `warranty_question` and `service_faq` on a cache miss, matching the token
budget targets in Section 4.5 ("booking flow 0 LLM calls; recall check 0 calls if cached...").
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.business import ServiceCatalog
from app.services.dialog import templates
from app.services.dialog.result import TurnResult
from app.services.dialog.state import DialogState
from app.services.llm.base import Message
from app.services.llm.prompts_loader import GROUNDED_ANSWER, load_prompt
from app.services.llm.recall_summaries import get_or_create_summary
from app.services.llm.response_cache import lookup as cache_lookup
from app.services.llm.response_cache import store as cache_store
from app.services.llm.router import AllProvidersUnavailableError, LLMRouter
from app.services.nhtsa.resolver import Ambiguous
from app.services.nhtsa.service import decode_vin, get_complaints_summary, get_recalls, resolve_vehicle
from app.services.retrieval import retrieve_kb_chunks

CHAT_MAX_TOKENS = 180
VOICE_MAX_TOKENS = 90


def handle_greeting(state: DialogState) -> TurnResult:
    return TurnResult(text=templates.GREETING)


def handle_goodbye(state: DialogState) -> TurnResult:
    return TurnResult(text=templates.GOODBYE)


def handle_thanks(state: DialogState) -> TurnResult:
    return TurnResult(text=templates.THANKS)


def handle_out_of_scope(state: DialogState) -> TurnResult:
    return TurnResult(text=templates.OUT_OF_SCOPE)


async def _identify_vehicle(db: AsyncSession, state: DialogState) -> tuple[str, str, int] | None:
    """Section 5.1: "VIN: decode via vPIC DecodeVinValues, then query recalls by
    year/make/model." Fills in whatever the VIN decode can supply, then requires all three of
    make/model/year (NHTSA's live lookups need an exact year/make/model, not a VIN alone)."""
    vehicle = state.vehicle_context or {}
    make, model, year = vehicle.get("make"), vehicle.get("model"), vehicle.get("year")

    if not (make and model and year) and vehicle.get("vin"):
        decoded = await decode_vin(db, vehicle["vin"])
        if decoded and decoded.get("make") and decoded.get("model") and decoded.get("model_year"):
            make = make or decoded["make"]
            model = model or decoded["model"]
            try:
                year = year or int(decoded["model_year"])
            except (TypeError, ValueError):
                pass
            state.vehicle_context = {**vehicle, "make": make, "model": model, "year": year}

    if not (make and model and year):
        return None
    return make, model, year


async def handle_recall_check(
    db: AsyncSession, state: DialogState, router: LLMRouter | None, channel: str = "chat"
) -> TurnResult:
    identified = await _identify_vehicle(db, state)
    if identified is None:
        return TurnResult(
            text="I can check recalls once I know your vehicle's year, make, and model -- could you share those?",
            flow_complete=False,
        )
    make, model, year = identified

    resolved = await resolve_vehicle(db, year, make, model)
    if resolved is None:
        return TurnResult(
            text=f"I couldn't find NHTSA data for a {year} {make} {model}. Could you double-check the year, make, and model?",
            flow_complete=False,
        )
    if isinstance(resolved, Ambiguous):
        options = ", ".join(resolved.candidates)
        return TurnResult(text=f"I found a few close matches: {options}. Which one is it?", flow_complete=False)

    recalls = await get_recalls(db, year, resolved.make, resolved.model)
    if not recalls:
        return TurnResult(
            text=(
                f"I don't see any open recalls on file for a {year} {resolved.make} {resolved.model}. "
                "Recalls are repaired free of charge; confirm your VIN status with our service team."
            )
        )

    max_shown = 1 if channel == "voice" else 3
    lines = []
    provider_used = None
    for recall in recalls[:max_shown]:
        summary_text, provider = await get_or_create_summary(db, recall, router)
        if provider not in ("cached", "template"):
            provider_used = provider
        lines.append(f"Campaign {recall.campaign_number} ({recall.component}): {summary_text} Remedy: {recall.remedy[:150]}")

    text = (
        f"I found {len(recalls)} open recall(s) for your {year} {resolved.make} {resolved.model}:\n"
        + "\n".join(lines)
        + "\nRecalls are repaired free of charge; confirm your VIN status with our service team. Want me to book a recall appointment?"
    )
    return TurnResult(text=text, llm_provider=provider_used)


async def handle_complaint_history(db: AsyncSession, state: DialogState) -> TurnResult:
    identified = await _identify_vehicle(db, state)
    if identified is None:
        return TurnResult(
            text="What's the year, make, and model of the vehicle you're asking about?", flow_complete=False
        )
    make, model, year = identified

    resolved = await resolve_vehicle(db, year, make, model)
    if resolved is None:
        return TurnResult(
            text=f"I couldn't find NHTSA data for a {year} {make} {model}. Could you double-check the year, make, and model?",
            flow_complete=False,
        )
    if isinstance(resolved, Ambiguous):
        options = ", ".join(resolved.candidates)
        return TurnResult(text=f"I found a few close matches: {options}. Which one is it?", flow_complete=False)

    summaries = await get_complaints_summary(db, year, resolved.make, resolved.model)
    if not summaries:
        return TurnResult(text=f"I don't have complaint data on file for a {year} {resolved.make} {resolved.model}.")

    lines = [
        f"{s.component}: {s.count} reported complaints (crash: {s.crash_count}, fire: {s.fire_count})"
        for s in summaries
    ]
    text = f"Here are the top reported issues for a {year} {resolved.make} {resolved.model}:\n" + "\n".join(lines)
    return TurnResult(text=text)


async def handle_pricing_estimate(db: AsyncSession, state: DialogState) -> TurnResult:
    service_code = state.slots.get("service_code")
    if not service_code:
        return TurnResult(text=templates.missing_slot_prompt("service_code"), flow_complete=False)

    result = await db.execute(select(ServiceCatalog).where(ServiceCatalog.code == service_code))
    service = result.scalar_one_or_none()
    if service is None:
        return TurnResult(text="I couldn't find pricing for that service; would you like to speak with an advisor?")

    labor_low = float(service.labor_hours_min or 0) * 145
    labor_high = float(service.labor_hours_max or 0) * 152
    low = labor_low + float(service.parts_cost_min or 0)
    high = labor_high + float(service.parts_cost_max or 0)
    text = (
        f"A {service.name.lower()} typically runs about ${low:,.0f} to ${high:,.0f}, "
        "including labor and parts. Your service advisor will confirm an exact price for your vehicle before any work begins."
    )
    return TurnResult(text=text)


async def handle_appointment_status(db: AsyncSession, state: DialogState) -> TurnResult:
    from app.core.security import lookup_hash
    from app.db.models.business import Appointment, Customer

    reference_code = state.slots.get("reference_code")
    phone = state.slots.get("phone")

    appointment = None
    if reference_code:
        result = await db.execute(select(Appointment).where(Appointment.reference_code == reference_code))
        appointment = result.scalar_one_or_none()
    elif phone:
        # Phone numbers are not unique across customers (households share lines, and the
        # synthetic Phase 1 dataset's narrow number range means it never even was for that
        # data); take any match rather than assuming exactly one.
        customer_result = await db.execute(
            select(Customer.customer_id).where(Customer.phone_hash == lookup_hash(phone)).limit(1)
        )
        customer_id = customer_result.scalar_one_or_none()
        if customer_id:
            result = await db.execute(
                select(Appointment)
                .where(Appointment.customer_id == customer_id)
                .order_by(Appointment.scheduled_start.desc())
                .limit(1)
            )
            appointment = result.scalar_one_or_none()
    else:
        return TurnResult(text=templates.missing_slot_prompt("reference_code_or_phone"), flow_complete=False)

    if appointment is None:
        return TurnResult(text="I couldn't find an appointment with that information. Could you double-check the confirmation code?")

    text = (
        f"Your appointment ({appointment.reference_code}) is scheduled for "
        f"{appointment.scheduled_start:%A, %B %d at %I:%M %p}, status: {appointment.status}."
    )
    return TurnResult(text=text)


async def handle_cancel_appointment(db: AsyncSession, state: DialogState) -> TurnResult:
    from app.services.scheduling.booking import cancel_appointment, verify_by_reference_and_last4

    reference_code, last4 = state.slots.get("reference_code"), state.slots.get("phone_last4")
    appointment = await verify_by_reference_and_last4(db, reference_code, last4)
    if appointment is None:
        return TurnResult(text="I couldn't verify that appointment with the confirmation code and phone digits given. Could you double check them?")

    await cancel_appointment(db, appointment)
    return TurnResult(text=f"Your appointment {appointment.reference_code} has been cancelled. No fee was charged.")


async def handle_reschedule_appointment(db: AsyncSession, state: DialogState) -> TurnResult:
    """Verifies the appointment, then hands off to the same 3-real-slots offer flow booking
    uses (Section 5.2); the manager stores the appointment_id being rescheduled in state and
    switches pending_slot to "reschedule_slot_choice" for the follow-up turn."""
    from app.services.scheduling.availability import find_available_slots

    reference_code, last4 = state.slots.get("reference_code"), state.slots.get("phone_last4")
    from app.services.scheduling.booking import verify_by_reference_and_last4

    appointment = await verify_by_reference_and_last4(db, reference_code, last4)
    if appointment is None:
        return TurnResult(text="I couldn't verify that appointment with the confirmation code and phone digits given. Could you double check them?")

    offers = await find_available_slots(db, appointment.location_id, appointment.service_code)
    if not offers:
        return TurnResult(
            text=f"Found appointment {appointment.reference_code}, but I couldn't find an open slot in the next few weeks. Connecting you with a service advisor.",
            escalate_reason="no_availability",
            contained=False,
        )

    from app.services.dialog.manager import _offer_to_dict

    state.slots["_reschedule_appointment_id"] = appointment.appointment_id
    state.last_offered_slots = [_offer_to_dict(o) for o in offers]
    state.pending_slot = "reschedule_slot_choice"
    options = "\n".join(f"{i + 1}. {o.start:%A, %B %d at %I:%M %p}" for i, o in enumerate(offers))
    return TurnResult(
        text=f"Found appointment {appointment.reference_code}. Here are the next available times:\n{options}\nWhich works best (1, 2, or 3)?",
        flow_complete=False,
    )


async def handle_parts_inquiry(state: DialogState) -> TurnResult:
    part = state.slots.get("part_or_service", "that part")
    text = (
        f"I've noted your question about {part}. Parts availability changes frequently, "
        "so I'm connecting you with a service advisor who can check current stock and pricing."
    )
    return TurnResult(text=text, escalate_reason="parts_inquiry", contained=False)


async def handle_grounded_question(
    db: AsyncSession, state: DialogState, question: str, intent: str, router: LLMRouter | None, max_tokens: int = CHAT_MAX_TOKENS
) -> TurnResult:
    """warranty_question and service_faq (Section 4.5, item 4: semantic cache before any RAG
    call; item 2: LLM only for a grounded answer from retrieved KB chunks)."""
    cached = await cache_lookup(db, question, intent)
    if cached is not None:
        return TurnResult(text=cached, cache_hit=True)

    chunks = await retrieve_kb_chunks(db, question, k=3)
    if not chunks:
        return TurnResult(
            text="I don't have enough information on file to answer that confidently. Let me connect you with a service advisor.",
            escalate_reason="no_grounded_answer",
            contained=False,
        )

    if router is None:
        # Both providers unavailable (Section 4.3 escalation trigger).
        return TurnResult(
            text="I found some related information but can't compose a full answer right now. Connecting you with a service advisor.",
            escalate_reason="llm_unavailable",
            contained=False,
        )

    context = "\n\n".join(f"[{c.title} - {c.section}] {c.content[:120 * 6]}" for c in chunks[:3])
    messages = [
        Message(role="system", content=load_prompt(GROUNDED_ANSWER)),
        Message(role="user", content=f"Context:\n{context}\n\nQuestion: {question}"),
    ]
    try:
        result = await router.generate(db, messages, max_tokens=max_tokens)
    except AllProvidersUnavailableError:
        return TurnResult(
            text="I'm having trouble reaching our answer service right now. Connecting you with a service advisor.",
            escalate_reason="llm_unavailable",
            contained=False,
        )

    await cache_store(db, question, result.text, intent)
    return TurnResult(
        text=result.text,
        llm_provider=result.provider,
        llm_tokens_in=result.tokens_in,
        llm_tokens_out=result.tokens_out,
    )
