# Demo script (about 7 minutes)

A live walkthrough of Meridian Assist for a dealership audience: the customer-facing site and
assistant, then the staff side handling what the assistant hands off.

Before starting: run `make setup data train up` (or `make dev` locally) so the site, chat,
voice, and staff portal are all live against a real database. Have a browser tab on the
public site and another signed out of `/login`.

## 1. The public site (30s)

Open the home page. Point out this is a normal dealership marketing site -- services,
locations, hours -- not a chatbot-first product. The assistant is additive, not a replacement
for the page.

## 2. Recall check for a real vehicle (45s)

Use the Recall Quick Check on the home page. Enter a real year/make/model (for example 2020
Honda Accord). This calls the live NHTSA recalls API, not a canned response -- point out the
"Data provided live by NHTSA" attribution and that the result reflects whatever NHTSA
currently has on file for that vehicle.

## 3. Chat booking (90s)

Open the chat widget (bottom right). Type a booking request end to end, for example:

1. "I need to book an oil change"
2. "2020 Toyota Camry"
3. "next Tuesday"
4. Your name
5. A phone number
6. Pick one of the 3 offered times

Narrate as it happens: this is a deterministic flow, not an LLM call -- intent
classification, slot filling, and real availability computation (technician shifts, bay
capacity, no double-booking) all run locally with zero LLM tokens spent. Show the resulting
confirmation code and the "Add to Calendar" link.

## 4. Voice booking (90s)

Click the microphone icon in the chat widget to switch to voice. Speak a short request (for
example "I need a tire rotation for my Honda Civic"). Call out: local speech-to-text
(faster-whisper), the same dialog manager as chat, and local text-to-speech streamed back
sentence by sentence so playback starts before the whole reply has synthesized. If time
allows, interrupt the assistant mid-reply to show barge-in cutting the audio off cleanly.

## 5. Safety escalation (60s)

Start a new chat and type something like "I smell smoke coming from the engine right now."
Show the assistant immediately connecting the customer to a service advisor rather than
attempting to answer -- this is a hard-coded safety rule, not a confidence judgment call.

## 6. Staff handling it live (90s)

Switch to the second browser tab, log in at `/login` as a service advisor (MFA is enforced
for the admin role; the seeded advisor account does not require it for a faster demo). Open
Escalations and show the safety escalation that was just created arriving in the Open column
in real time over WebSocket, with no page refresh. Assign it, reply, and resolve it, showing
the kanban update live.

## 7. Revenue dashboard and assistant ROI (60s)

Navigate to the Executive Overview and Revenue Analytics pages. Change the date range preset
and show the KPIs and charts update. Point out the Assistant Performance page specifically:
containment rate, average LLM calls per turn, and the token-budget-driven cost story -- the
concrete case for why offloading routine bookings and recall checks to a zero-token
deterministic flow matters at dealership scale.

## Closing note

Mention what is intentionally out of scope for this demo: OWASP ZAP dynamic scanning and a
Lighthouse run both need a deployed, internet-reachable instance and are documented as such
in `docs/security.md`, not silently skipped.
