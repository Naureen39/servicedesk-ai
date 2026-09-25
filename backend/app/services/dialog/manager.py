"""Dialog manager (Section 4.2): orchestrates one customer turn end to end -- sentiment,
intent classification, global interrupts, slot extraction/collection, per-intent flow
dispatch, the escalation gate (Section 4.3), and per-conversation token budget enforcement
(Section 4.5, item 7). This is the seam every channel adapter calls through.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.assistant import Conversation, Message
from app.services import settings_store
from app.services.dialog import flows, policy, templates
from app.services.dialog.result import TurnResult
from app.services.dialog.state import (
    GLOBAL_INTERRUPT_INTENTS,
    MAX_CLARIFICATION_ATTEMPTS,
    MAX_SLOT_ATTEMPTS,
    TOKEN_BUDGET_PER_CONVERSATION,
    DialogState,
)
from app.services.llm.router import LLMRouter
from app.services.nlu.intent_classifier import IntentClassifierNotTrained, predict_intent
from app.services.nlu.slots import extract_all

TEMPLATE_ONLY_INTENTS = {"greeting", "goodbye", "thanks", "out_of_scope"}
IMMEDIATE_ESCALATION_INTENTS = policy.ESCALATING_INTENTS


async def _log_message(
    db: AsyncSession, conversation_id: str, turn: int, sender: str, text: str,
    intent: str | None = None, confidence: float | None = None, slots: dict | None = None,
    latency_ms: int | None = None, tokens_in: int = 0, tokens_out: int = 0,
    provider: str | None = None, cache_hit: bool = False,
) -> Message:
    message = Message(
        message_id=f"MSG-{uuid.uuid4().hex[:10].upper()}",
        conversation_id=conversation_id,
        turn=turn,
        sender=sender,
        text=text,
        intent=intent,
        confidence=confidence,
        slots=slots,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        provider=provider,
        cache_hit=cache_hit,
        created_at=datetime.now(UTC),
    )
    db.add(message)
    await db.flush()
    return message


async def _recent_messages(db: AsyncSession, conversation_id: str, limit: int = 6) -> list[Message]:
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.turn.desc()).limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def _escalate(
    db: AsyncSession, conversation: Conversation, state: DialogState, reason: str, last_messages: list[Message]
) -> TurnResult:
    escalation = await policy.create_escalation(
        db,
        conversation_id=conversation.conversation_id,
        reason=reason,
        vehicle_context=state.vehicle_context,
        intent=state.intent,
        slots=state.slots,
        last_messages=last_messages,
    )
    conversation.escalated = True
    text = templates.ESCALATION_CONFIRMATION[escalation.priority]
    if reason == "safety_concern":
        text = templates.SAFETY_CONCERN_ACK + " " + text
    elif reason == "complaint":
        text = templates.COMPLAINT_ACK + " " + text
    elif reason == "speak_to_human":
        text = templates.SPEAK_TO_HUMAN_ACK
    state.reset_flow()
    return TurnResult(text=text, contained=False, escalate_reason=reason)


async def handle_turn(
    db: AsyncSession,
    conversation: Conversation,
    user_text: str,
    router: LLMRouter | None,
    channel: str = "chat",
) -> TurnResult:
    state = DialogState.from_dict(conversation.state)
    state.turn_count += 1
    turn_number = state.turn_count

    await _log_message(db, conversation.conversation_id, turn_number * 2 - 1, "customer", user_text)

    # --- Sentiment (Section 4.1, escalation signal for Section 4.3) ---
    # Skipped for narrow structured-answer turns (phone, date, reference code, slot choice):
    # SST-2 is a movie-review classifier applied out of domain, and short data-shaped text
    # like a phone number gets a confidently noisy score from it far too often to be a
    # meaningful "the customer sounds upset" signal there.
    if state.pending_slot is None:
        try:
            from app.services.nlu.sentiment import is_strongly_negative

            negative = is_strongly_negative(user_text)
        except Exception:
            negative = False
        state.negative_sentiment_streak = state.negative_sentiment_streak + 1 if negative else 0
    else:
        state.negative_sentiment_streak = 0

    # --- Slot extraction, computed up front so we can tell a genuine global interrupt
    # ("actually, let me talk to a human") apart from a slot answer the classifier happens to
    # mislabel (a bare phone number like "614-555-0199" scores high on speak_to_human, since
    # data-shaped text doesn't resemble any of its natural-language training utterances). ---
    extracted = extract_all(user_text)
    if state.pending_slot in ("name", "part_or_service") and not extracted.get(state.pending_slot):
        extracted[state.pending_slot] = user_text.strip()

    # Choice slots (a number/ordinal, or a yes/no read-back confirmation) are always "answering
    # the slot we just asked for" by construction, so they must never be preempted by the
    # global-interrupt check below even if the classifier scores them as e.g. "goodbye" --
    # the same class of bug Phase 4 fixed for bare phone numbers scoring as speak_to_human.
    _choice_slots = ("slot_choice", "reschedule_slot_choice", "voice_confirm_phone")
    pending_slot_answered = bool(state.pending_slot) and (
        state.pending_slot in _choice_slots or _slot_filled(state, extracted, state.pending_slot)
    )

    # --- Intent classification ---
    try:
        top_intent, confidence = predict_intent(user_text)
    except IntentClassifierNotTrained:
        top_intent, confidence = "out_of_scope", 0.0

    result: TurnResult

    # --- Global interrupts override any in-progress flow (Section 4.2), unless this message
    # is simply answering the slot we just asked for. ---
    if top_intent in GLOBAL_INTERRUPT_INTENTS and confidence >= settings_store.confidence_threshold() and not pending_slot_answered:
        state.reset_flow()
        state.intent = top_intent

    elif state.pending_slot == "slot_choice":
        result = await _handle_slot_choice(db, conversation, state, user_text)
        return await _finalize(db, conversation, state, result, turn_number, top_intent, confidence)

    elif state.pending_slot == "reschedule_slot_choice":
        result = await _handle_reschedule_slot_choice(db, conversation, state, user_text)
        return await _finalize(db, conversation, state, result, turn_number, top_intent, confidence)

    elif state.pending_slot == "voice_confirm_phone":
        result = await _handle_voice_confirm_phone(db, conversation, state, user_text, router, channel)
        return await _finalize(db, conversation, state, result, turn_number, top_intent, confidence)

    elif state.intent is None:
        if confidence < settings_store.confidence_threshold():
            if state.clarification_attempts < MAX_CLARIFICATION_ATTEMPTS:
                state.clarification_attempts += 1
                result = TurnResult(text=templates.CLARIFICATION_PROMPT, flow_complete=False)
                return await _finalize(db, conversation, state, result, turn_number, top_intent, confidence)
            last_messages = await _recent_messages(db, conversation.conversation_id)
            result = await _escalate(db, conversation, state, "low_confidence", last_messages)
            return await _finalize(db, conversation, state, result, turn_number, top_intent, confidence)
        state.intent = top_intent
        state.clarification_attempts = 0

    # --- Escalation gate: intents that always escalate ---
    if state.intent in IMMEDIATE_ESCALATION_INTENTS:
        last_messages = await _recent_messages(db, conversation.conversation_id)
        result = await _escalate(db, conversation, state, state.intent, last_messages)
        return await _finalize(db, conversation, state, result, turn_number, top_intent, confidence)

    # --- Escalation gate: sentiment strongly negative for 2 consecutive turns ---
    if policy.should_escalate_sentiment(state.negative_sentiment_streak):
        last_messages = await _recent_messages(db, conversation.conversation_id)
        result = await _escalate(db, conversation, state, "negative_sentiment", last_messages)
        return await _finalize(db, conversation, state, result, turn_number, top_intent, confidence)

    # --- Token budget hard cap ---
    if conversation.tokens_used_total >= TOKEN_BUDGET_PER_CONVERSATION:
        last_messages = await _recent_messages(db, conversation.conversation_id)
        result = await _escalate(db, conversation, state, "token_budget_exceeded", last_messages)
        return await _finalize(db, conversation, state, result, turn_number, top_intent, confidence)

    # --- Slot application (extraction already computed above) ---
    if state.pending_slot and not _slot_filled(state, extracted, state.pending_slot):
        attempts = state.attempt_counts.get(state.pending_slot, 0) + 1
        state.attempt_counts[state.pending_slot] = attempts
        if policy.should_escalate_slot_failure(attempts, MAX_SLOT_ATTEMPTS):
            last_messages = await _recent_messages(db, conversation.conversation_id)
            result = await _escalate(db, conversation, state, "repeated_slot_failure", last_messages)
            return await _finalize(db, conversation, state, result, turn_number, top_intent, confidence)

    state.apply_extracted_slots(extracted)

    # --- Dispatch ---
    result = await _dispatch(db, conversation, state, user_text, router, channel)

    return await _finalize(db, conversation, state, result, turn_number, top_intent, confidence)


def _slot_filled(state: DialogState, extracted: dict, slot_name: str) -> bool:
    if slot_name == "vehicle":
        return bool(extracted.get("make") or extracted.get("vin"))
    if slot_name == "reference_code_or_phone":
        return bool(extracted.get("reference_code") or extracted.get("phone"))
    key_map = {"service_code": "service_code", "phone": "phone", "phone_last4": "phone_last4",
               "reference_code": "reference_code", "part_or_service": "part_or_service",
               "date_window": "date", "name": "name"}
    return bool(extracted.get(key_map.get(slot_name, slot_name)))


async def _dispatch(
    db: AsyncSession, conversation: Conversation, state: DialogState, user_text: str, router: LLMRouter | None, channel: str
) -> TurnResult:
    intent = state.intent

    if intent in TEMPLATE_ONLY_INTENTS:
        handler = {
            "greeting": flows.handle_greeting,
            "goodbye": flows.handle_goodbye,
            "thanks": flows.handle_thanks,
            "out_of_scope": flows.handle_out_of_scope,
        }[intent]
        result = handler(state)
        state.reset_flow()
        return result

    missing = state.missing_slots()
    if missing:
        slot = missing[0]
        state.pending_slot = slot
        return TurnResult(text=templates.missing_slot_prompt(slot), flow_complete=False)

    state.pending_slot = None

    if channel == "voice" and not state.phone_confirmed:
        phone_value = state.slots.get("phone") or state.slots.get("phone_last4")
        if phone_value:
            from app.services.voice.spokenize import spoken_digits

            state.pending_slot = "voice_confirm_phone"
            last4 = "".join(ch for ch in phone_value if ch.isdigit())[-4:]
            return TurnResult(text=f"I have your phone ending in {spoken_digits(last4)}. Is that correct?", flow_complete=False)

    if intent == "recall_check":
        result = await flows.handle_recall_check(db, state, router, channel=channel)
    elif intent == "complaint_history":
        result = await flows.handle_complaint_history(db, state)
    elif intent == "pricing_estimate":
        result = await flows.handle_pricing_estimate(db, state)
    elif intent == "appointment_status":
        result = await flows.handle_appointment_status(db, state)
    elif intent == "cancel_appointment":
        result = await flows.handle_cancel_appointment(db, state)
    elif intent == "reschedule_appointment":
        result = await flows.handle_reschedule_appointment(db, state)
    elif intent == "parts_inquiry":
        result = await flows.handle_parts_inquiry(state)
    elif intent in ("warranty_question", "service_faq"):
        max_tokens = flows.VOICE_MAX_TOKENS if channel == "voice" else flows.CHAT_MAX_TOKENS
        result = await flows.handle_grounded_question(db, state, user_text, intent, router, max_tokens)
    elif intent == "book_service":
        result = await _handle_booking_ready(db, conversation, state)
    else:
        result = TurnResult(text=templates.OUT_OF_SCOPE)

    if result.escalate_reason:
        last_messages = await _recent_messages(db, conversation.conversation_id)
        await policy.create_escalation(
            db,
            conversation_id=conversation.conversation_id,
            reason=result.escalate_reason,
            vehicle_context=state.vehicle_context,
            intent=state.intent,
            slots=state.slots,
            last_messages=last_messages,
        )
        conversation.escalated = True

    if result.flow_complete:
        state.reset_flow()
    return result


async def _default_location_id(db: AsyncSession) -> int | None:
    from app.db.models.business import Location

    result = await db.execute(select(Location.location_id).order_by(Location.location_id).limit(1))
    return result.scalar_one_or_none()


def _offer_to_dict(offer) -> dict:
    return {
        "start": offer.start.isoformat(), "end": offer.end.isoformat(),
        "technician_id": offer.technician_id, "bay_number": offer.bay_number, "location_id": offer.location_id,
    }


def _offer_from_dict(data: dict):
    from app.services.scheduling.availability import SlotOffer

    return SlotOffer(
        start=datetime.fromisoformat(data["start"]), end=datetime.fromisoformat(data["end"]),
        technician_id=data["technician_id"], bay_number=data["bay_number"], location_id=data["location_id"],
    )


async def _handle_booking_ready(db: AsyncSession, conversation: Conversation, state: DialogState) -> TurnResult:
    """All base booking slots (service, vehicle, date_window, name, phone) are filled; offer
    3 real slots (Section 4.2 / 5.2: "offer 3 real slots") before collecting confirmation."""
    from app.services.scheduling.availability import PartsUnavailableError, find_available_slots

    location_id = conversation.location_id or await _default_location_id(db)
    if location_id is None:
        return TurnResult(text="I'm unable to look up availability right now. Connecting you with a service advisor.", escalate_reason="no_location", contained=False)

    try:
        offers = await find_available_slots(db, location_id, state.slots["service_code"])
    except PartsUnavailableError:
        return TurnResult(
            text="That recall repair needs a part that's currently out of stock. I've flagged this so we can order it and follow up with you.",
            escalate_reason="parts_unavailable",
            contained=False,
        )
    if not offers:
        return TurnResult(text="I couldn't find an open slot in the next few weeks. Connecting you with a service advisor to find a time.", escalate_reason="no_availability", contained=False)

    state.last_offered_slots = [_offer_to_dict(o) for o in offers]
    state.pending_slot = "slot_choice"
    options = "\n".join(f"{i + 1}. {o.start:%A, %B %d at %I:%M %p}" for i, o in enumerate(offers))
    return TurnResult(text=f"Here are the next available times:\n{options}\nWhich works best (1, 2, or 3)?", flow_complete=False)


def _parse_yes_no(user_text: str) -> bool | None:
    lowered = user_text.strip().lower()
    if any(w in lowered for w in ("yes", "yeah", "yep", "correct", "that's right", "right", "affirmative")):
        return True
    if any(w in lowered for w in ("no", "nope", "wrong", "incorrect", "not right")):
        return False
    return None


async def _handle_voice_confirm_phone(
    db: AsyncSession, conversation: Conversation, state: DialogState, user_text: str, router: LLMRouter | None, channel: str
) -> TurnResult:
    answer = _parse_yes_no(user_text)
    if answer is None:
        return TurnResult(text="Sorry, was that a yes or a no?", flow_complete=False)
    if answer:
        state.phone_confirmed = True
        state.pending_slot = None
        return await _dispatch(db, conversation, state, user_text, router, channel)
    state.slots.pop("phone", None)
    state.slots.pop("phone_last4", None)
    # Setting this to "phone" (not None) matters: it's what makes the pre-existing
    # bare-phone-number-misclassified-as-speak_to_human protection (pending_slot_answered)
    # apply to the retry below, the same way it applies to the first attempt at this slot.
    state.pending_slot = "phone"
    return TurnResult(text="No problem -- what's the best phone number?", flow_complete=False)


def _parse_slot_choice(user_text: str) -> int | None:
    import re

    match = re.search(r"\b([123])\b", user_text)
    if match:
        return int(match.group(1)) - 1
    lowered = user_text.lower()
    if "first" in lowered:
        return 0
    if "second" in lowered:
        return 1
    if "third" in lowered or "last" in lowered:
        return 2
    return None


async def _handle_slot_choice(db: AsyncSession, conversation: Conversation, state: DialogState, user_text: str) -> TurnResult:
    from app.services.scheduling.booking import LeadTimeError, SlotConflictError, create_booking

    offers = state.last_offered_slots
    choice_index = _parse_slot_choice(user_text)

    if choice_index is None or not (0 <= choice_index < len(offers)):
        attempts = state.attempt_counts.get("slot_choice", 0) + 1
        state.attempt_counts["slot_choice"] = attempts
        if policy.should_escalate_slot_failure(attempts, MAX_SLOT_ATTEMPTS):
            return await _escalate(db, conversation, state, "repeated_slot_failure", await _recent_messages(db, conversation.conversation_id))
        return TurnResult(text="Sorry, which option would you like -- 1, 2, or 3?", flow_complete=False)

    offer = _offer_from_dict(offers[choice_index])
    customer_id, vehicle_id = await _resolve_or_create_customer_and_vehicle(db, conversation, state)

    try:
        appointment = await create_booking(
            db,
            customer_id=customer_id,
            vehicle_id=vehicle_id,
            service_code=state.slots["service_code"],
            offer=offer,
            channel=f"assistant_{conversation.channel or 'chat'}",
        )
    except SlotConflictError:
        # Section 5.2 DoD: under real concurrency, the loser of a race for the same slot must
        # recover gracefully rather than error out -- tell the customer and let them pick again.
        return TurnResult(
            text="Sorry, that time was just booked by another customer. Could you pick a different option (1, 2, or 3)?",
            flow_complete=False,
        )
    except LeadTimeError:
        return TurnResult(text="Same-day bookings need at least 2 hours' notice. Could you pick a different option?", flow_complete=False)

    conversation.resulting_appointment_id = appointment.appointment_id
    text = (
        f"You're booked for {offer.start:%A, %B %d at %I:%M %p}. "
        f"Your confirmation code is {appointment.reference_code}. We'll see you then!"
    )
    state.reset_flow()
    return TurnResult(text=text)


async def _handle_reschedule_slot_choice(db: AsyncSession, conversation: Conversation, state: DialogState, user_text: str) -> TurnResult:
    from sqlalchemy import select as sa_select

    from app.db.models.business import Appointment
    from app.services.scheduling.booking import LeadTimeError, SlotConflictError, reschedule_appointment

    offers = state.last_offered_slots
    choice_index = _parse_slot_choice(user_text)

    if choice_index is None or not (0 <= choice_index < len(offers)):
        attempts = state.attempt_counts.get("reschedule_slot_choice", 0) + 1
        state.attempt_counts["reschedule_slot_choice"] = attempts
        if policy.should_escalate_slot_failure(attempts, MAX_SLOT_ATTEMPTS):
            return await _escalate(db, conversation, state, "repeated_slot_failure", await _recent_messages(db, conversation.conversation_id))
        return TurnResult(text="Sorry, which option would you like -- 1, 2, or 3?", flow_complete=False)

    offer = _offer_from_dict(offers[choice_index])
    appointment_id = state.slots["_reschedule_appointment_id"]
    result = await db.execute(sa_select(Appointment).where(Appointment.appointment_id == appointment_id))
    appointment = result.scalar_one()

    try:
        await reschedule_appointment(db, appointment, offer)
    except SlotConflictError:
        return TurnResult(text="Sorry, that time was just booked by another customer. Could you pick a different option (1, 2, or 3)?", flow_complete=False)
    except LeadTimeError:
        return TurnResult(text="Same-day bookings need at least 2 hours' notice. Could you pick a different option?", flow_complete=False)

    text = f"Done -- your appointment {appointment.reference_code} is now scheduled for {offer.start:%A, %B %d at %I:%M %p}."
    state.reset_flow()
    return TurnResult(text=text)


async def _resolve_or_create_customer_and_vehicle(db: AsyncSession, conversation: Conversation, state: DialogState) -> tuple[str, str]:
    from app.core.security import lookup_hash
    from app.db.models.business import Customer, Vehicle
    from app.services.customers import encrypt_value

    phone = state.slots.get("phone", "")
    phone_hash = lookup_hash(phone) if phone else None

    customer_id = conversation.customer_id
    if customer_id is None and phone_hash:
        # See flows.py's identical comment: phone numbers are not guaranteed unique, so take
        # any match rather than assuming exactly one row.
        result = await db.execute(select(Customer.customer_id).where(Customer.phone_hash == phone_hash).limit(1))
        customer_id = result.scalar_one_or_none()

    if customer_id is None:
        customer_id = f"CUST-{uuid.uuid4().hex[:10].upper()}"
        name = state.slots.get("name", "")
        first_name, _, last_name = name.partition(" ")
        db.add(
            Customer(
                customer_id=customer_id,
                first_name=first_name or None,
                last_name=last_name or None,
                phone_encrypted=await encrypt_value(db, phone) if phone else None,
                phone_hash=phone_hash,
                created_at=datetime.now(UTC),
                preferred_location_id=conversation.location_id,
            )
        )
        await db.flush()
        conversation.customer_id = customer_id

    vehicle = state.vehicle_context or {}
    vehicle_id = None
    if vehicle.get("make") and vehicle.get("model"):
        result = await db.execute(
            select(Vehicle.vehicle_id).where(
                Vehicle.customer_id == customer_id, Vehicle.make == vehicle["make"], Vehicle.model == vehicle["model"]
            )
        )
        vehicle_id = result.scalar_one_or_none()

    if vehicle_id is None:
        vehicle_id = f"VEH-{uuid.uuid4().hex[:10].upper()}"
        db.add(
            Vehicle(
                vehicle_id=vehicle_id,
                customer_id=customer_id,
                year=vehicle.get("year"),
                make=vehicle.get("make"),
                model=vehicle.get("model"),
                vin=vehicle.get("vin"),
            )
        )
        await db.flush()

    return customer_id, vehicle_id


async def _finalize(
    db: AsyncSession, conversation: Conversation, state: DialogState, result: TurnResult,
    turn_number: int, detected_intent: str, confidence: float,
) -> TurnResult:
    conversation.tokens_used_total += result.llm_tokens_in + result.llm_tokens_out
    conversation.intent = state.intent or detected_intent
    if result.contained is False:
        conversation.contained = False
    elif conversation.contained is None:
        conversation.contained = True

    conversation.state = state.to_dict()

    message = await _log_message(
        db, conversation.conversation_id, turn_number * 2, "assistant", result.text,
        intent=detected_intent, confidence=confidence, slots=state.slots,
        tokens_in=result.llm_tokens_in, tokens_out=result.llm_tokens_out,
        provider=result.llm_provider, cache_hit=result.cache_hit,
    )
    result.message_id = message.message_id
    await db.commit()
    return result
