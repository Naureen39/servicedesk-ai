"""Templated (zero-LLM) response text (Section 4.2: "Every prompt for a missing slot is a
template, not an LLM call") and the per-intent canned copy for intents that never need the
LLM (Section 4.5, item 1: "Deterministic first").
"""

from __future__ import annotations

GREETING = "Hi, I'm Meridian Assist. I can help with service questions, recalls, pricing, or booking an appointment. What can I help with today?"
GOODBYE = "Thanks for reaching out to Meridian Auto Group. Have a great day!"
THANKS = "You're welcome! Is there anything else I can help with?"
OUT_OF_SCOPE = "I'm the automotive service assistant for Meridian Auto Group, so I can't help with that, but I'm glad to help with service questions, recalls, pricing, or booking an appointment."

SPEAK_TO_HUMAN_ACK = "Of course, connecting you with a service advisor now. A team member will follow up with you as soon as possible."
COMPLAINT_ACK = "I'm sorry to hear about that experience. I've flagged this for a service manager to follow up with you personally."
SAFETY_CONCERN_ACK = "That sounds like a safety concern. I've flagged this as urgent for our service team, and someone will reach out right away. If this is an emergency, please pull over safely and call for roadside assistance."

MISSING_SLOT_PROMPTS = {
    "service_code": "What service would you like to schedule (for example, an oil change, tire rotation, or brake inspection)?",
    "vehicle": "What's the year, make, and model of your vehicle?",
    "date_window": "What day works best for you?",
    "name": "Can I get your name for the appointment?",
    "phone": "What's the best phone number to reach you at?",
    "reference_code": "Do you have your confirmation code? It looks like MRD-XXXXXX.",
    "reference_code_or_phone": "Can you give me your confirmation code, or the phone number on the appointment?",
    "phone_last4": "For verification, what are the last 4 digits of the phone number on the appointment?",
    "part_or_service": "Which part or service are you asking about?",
}

CLARIFICATION_PROMPT = "Sorry, I didn't quite catch that. Could you tell me a bit more about what you need help with?"

ESCALATION_CONFIRMATION = {
    "P1": "This has been escalated to our team as urgent. Expect a response within 15 minutes.",
    "P2": "This has been escalated to a service manager. Expect a response within 2 hours.",
    "P3": "This has been passed to our team. Expect a response by the next business day.",
}

TOKEN_BUDGET_EXCEEDED = "This conversation has covered a lot of ground -- let me connect you with a service advisor to make sure you get everything you need."


def missing_slot_prompt(slot: str) -> str:
    return MISSING_SLOT_PROMPTS.get(slot, "Could you give me a bit more information?")
