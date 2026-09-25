"""Conversation state (Section 4.2): current intent, filled slots, pending slot, attempt
counters, vehicle context, last offered time slots -- stored as JSONB on `conversations.state`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED_SLOTS: dict[str, list[str]] = {
    "greeting": [],
    "goodbye": [],
    "thanks": [],
    "recall_check": ["vehicle"],
    "complaint_history": ["vehicle"],
    "book_service": ["service_code", "vehicle", "date_window", "name", "phone"],
    "reschedule_appointment": ["reference_code", "phone_last4"],
    "cancel_appointment": ["reference_code", "phone_last4"],
    "appointment_status": ["reference_code_or_phone"],
    "pricing_estimate": ["service_code"],
    "warranty_question": [],
    "service_faq": [],
    "parts_inquiry": ["part_or_service"],
    "complaint": [],
    "safety_concern": [],
    "speak_to_human": [],
    "out_of_scope": [],
}

GLOBAL_INTERRUPT_INTENTS = {"speak_to_human", "safety_concern", "goodbye"}
MAX_SLOT_ATTEMPTS = 2
MAX_CLARIFICATION_ATTEMPTS = 1
CONFIDENCE_THRESHOLD = 0.55
TOKEN_BUDGET_PER_CONVERSATION = 3000


@dataclass
class DialogState:
    intent: str | None = None
    slots: dict[str, Any] = field(default_factory=dict)
    pending_slot: str | None = None
    attempt_counts: dict[str, int] = field(default_factory=dict)
    vehicle_context: dict[str, Any] | None = None
    last_offered_slots: list[dict[str, Any]] = field(default_factory=list)
    clarification_attempts: int = 0
    negative_sentiment_streak: int = 0
    turn_count: int = 0
    phone_confirmed: bool = False
    """Phase 6 item 7: voice-only read-back gate ("I have your phone ending in 4 5 1 2, is
    that correct?"). Set once per flow the first time a phone/phone_last4 slot is confirmed
    by the caller; reset on reset_flow() so a later flow in the same call re-confirms."""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DialogState:
        if not data:
            return cls()
        return cls(
            intent=data.get("intent"),
            slots=dict(data.get("slots") or {}),
            pending_slot=data.get("pending_slot"),
            attempt_counts=dict(data.get("attempt_counts") or {}),
            vehicle_context=data.get("vehicle_context"),
            last_offered_slots=list(data.get("last_offered_slots") or []),
            clarification_attempts=data.get("clarification_attempts", 0),
            negative_sentiment_streak=data.get("negative_sentiment_streak", 0),
            turn_count=data.get("turn_count", 0),
            phone_confirmed=data.get("phone_confirmed", False),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "slots": self.slots,
            "pending_slot": self.pending_slot,
            "attempt_counts": self.attempt_counts,
            "vehicle_context": self.vehicle_context,
            "last_offered_slots": self.last_offered_slots,
            "clarification_attempts": self.clarification_attempts,
            "negative_sentiment_streak": self.negative_sentiment_streak,
            "turn_count": self.turn_count,
            "phone_confirmed": self.phone_confirmed,
        }

    def reset_flow(self) -> None:
        self.intent = None
        self.slots = {}
        self.pending_slot = None
        self.attempt_counts = {}
        self.clarification_attempts = 0
        self.phone_confirmed = False
        # vehicle_context and turn_count/sentiment streak intentionally survive a flow reset,
        # since a vehicle mentioned once should carry over to the next intent (Section 4.2).

    def missing_slots(self) -> list[str]:
        required = REQUIRED_SLOTS.get(self.intent or "", [])
        missing = []
        for slot in required:
            if slot == "vehicle":
                if not self._has_vehicle():
                    missing.append(slot)
            elif slot == "reference_code_or_phone":
                if not (self.slots.get("reference_code") or self.slots.get("phone")):
                    missing.append(slot)
            elif not self.slots.get(slot):
                missing.append(slot)
        return missing

    def _has_vehicle(self) -> bool:
        vehicle = self.vehicle_context or {}
        return bool(vehicle.get("vin") or (vehicle.get("make") and vehicle.get("model")))

    def apply_extracted_slots(self, extracted: dict[str, Any]) -> None:
        if extracted.get("vin"):
            self.vehicle_context = {**(self.vehicle_context or {}), "vin": extracted["vin"]}
        if extracted.get("make") or extracted.get("model") or extracted.get("year"):
            vc = dict(self.vehicle_context or {})
            if extracted.get("make"):
                vc["make"] = extracted["make"]
            if extracted.get("model"):
                vc["model"] = extracted["model"]
            if extracted.get("year"):
                vc["year"] = extracted["year"]
            self.vehicle_context = vc

        if extracted.get("phone"):
            self.slots["phone"] = extracted["phone"]
        if extracted.get("phone_last4"):
            self.slots["phone_last4"] = extracted["phone_last4"]
        if extracted.get("reference_code"):
            self.slots["reference_code"] = extracted["reference_code"]
        if extracted.get("service_code"):
            self.slots["service_code"] = extracted["service_code"]
        if extracted.get("date"):
            self.slots["date_window"] = extracted["date"].isoformat()
        if extracted.get("part_or_service"):
            self.slots["part_or_service"] = extracted["part_or_service"]
        if extracted.get("name"):
            self.slots["name"] = extracted["name"]
