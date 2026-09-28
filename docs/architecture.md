# Architecture

## High-level flow

```
Customer (web chat / browser voice)
        |
        v
Channel adapter (app/services/channel/): web_chat.py (text passthrough), voice.py (STT on
raw PCM16 via faster-whisper)
        |
        v
PII redaction (app/services/pii.py) -> semantic response cache (app/services/llm/response_cache.py)
        |                                          | cache hit -> response
        v (cache miss)
Local NLU (app/services/nlu/): intent classifier (Logistic Regression on bge-small
embeddings, calibrated) + rule-based slot extractor (VIN, year/make/model, date, phone,
service type)
        |
        v
Dialog manager and policy (app/services/dialog/manager.py, flows.py, policy.py): a
finite-state flow per intent, plus the escalation gate (low confidence, repeated slot
failure, negative sentiment streak, explicit "speak to a human")
        |
        +--> NHTSA service (app/services/nhtsa/): recalls, complaints, VIN decode, cached
        +--> Scheduling engine (app/services/scheduling/): availability computation, conflict
             checking, booking
        +--> Knowledge retrieval (app/services/retrieval.py): pgvector similarity search over
             the dealership knowledge base
        +--> LLM router (app/services/llm/router.py): Groq primary, Gemini fallback, used only
             when a deterministic flow or template can't answer
        |
        v
Response composer (templates first, LLM output second)
        |
        v
Text-to-speech (voice only, app/services/voice/tts.py, local Kokoro)
        |
        v
Every turn logged (conversation, intent, confidence, LLM tokens, outcome) to Postgres, read
by the analytics dashboards (app/api/v1/analytics.py)
```

Booking is representative of the "no LLM call" path: intent classification, slot filling,
availability, and confirmation are all deterministic code, not LLM calls (verified directly
in `backend/tests/test_scripted_conversations.py`'s LLM-budget assertion).

## Backend layout (`backend/app/`)

- `api/v1/` — routers: `auth`, `chat`, `voice`, `public`, `appointments`, `staff`,
  `analytics`, `admin`, `test_console`. Aggregated in `api/v1/router.py`.
- `core/` — settings (`config.py`), password/TOTP/session-token handling
  (`security.py`), permission codes and the role -> permission matrix
  (`permissions.py`), rate limiting (`rate_limit.py`), typed problem-details
  exceptions (`exceptions.py`).
- `db/` — SQLAlchemy async models (`models/`), the async session factory
  (`base.py`), Alembic migrations (`../../data/migrations/`, shared with the dataset
  loader).
- `services/`
  - `nlu/` — `catalog_cache.py` (in-memory service/vehicle reference cache),
    `intent_classifier.py`, `slots.py`, `sentiment.py`.
  - `dialog/` — `manager.py` (turn dispatch), `flows.py` (per-intent state
    machines), `policy.py` (the escalation gate), `state.py`, `portal_feed.py`
    (WebSocket pub/sub to the staff portal).
  - `llm/` — `router.py` (primary/fallback with live failover), `groq_provider.py`,
    `gemini_provider.py`, `response_cache.py`, `recall_summaries.py`.
  - `nhtsa/` — `client.py`, `resolver.py`, `service.py` (recalls/complaints/VIN,
    cached).
  - `scheduling/` — `availability.py` (shift/bay/skill-aware slot search),
    `booking.py` (conflict-checked booking).
  - `voice/` — `stt.py` (faster-whisper), `tts.py` (Kokoro), `session.py`
    (WebSocket voice session: reader loop, barge-in, sentence-streamed TTS),
    `spokenize.py` (text normalization for speech).
  - `channel/` — the `ChannelAdapter` interface (`base.py`) implemented by
    `web_chat.py` and `voice.py`, keeping `handle_turn` channel-agnostic.
  - `kb_admin.py`, `escalation_workflow.py`, `rbac.py`, `settings_store.py`,
    `customers.py`, `embeddings.py`, `retrieval.py`, `audit.py`.
- `schemas/` — Pydantic request/response DTOs.

## Frontend layout (`frontend/src/`)

- `pages/` — public marketing/booking pages (`Home`, `Book`, `Recalls`,
  `Services`, ...) and `pages/portal/` — the staff console (executive
  overview, revenue/operations/technician/recall analytics, live
  conversations, escalations, appointments, knowledge base, admin, test
  console).
- `components/` — `ChatWidget.tsx` and `VoiceModal.tsx` (customer-facing
  assistant), `RecallQuickCheck.tsx`, `FaqAccordion.tsx`, and `components/ui/`
  (design-system primitives) and `components/portal/` (charts, KPI cards, date
  range picker).
- `lib/` — `api.ts` (public API client), `portalApi.ts` (authenticated staff API
  client), `auth.ts`, `useChatSession.ts`, `useDateRange.ts`, formatting helpers.

## Data flow for a booking turn (no LLM call)

1. `POST /api/v1/chat/message` receives the raw text.
2. `ChannelAdapter.receive()` wraps it in a `Turn`.
3. `handle_turn()` (`dialog/manager.py`) loads the conversation's `DialogState`, runs slot
   extraction (`nlu/slots.py`) for whatever's still missing, and dispatches to the booking
   flow once intent + vehicle + service + name + phone are all filled.
4. `scheduling/availability.find_available_slots()` computes up to 3 real open slots from
   `technicians`, `shift_templates`, `bays`, and existing `appointments` -- no LLM call.
5. On the customer's slot choice, `scheduling/booking.create_booking()` re-checks for a
   conflict at commit time and inserts the `Appointment` row.
6. The turn, its intent, confidence, and outcome are logged to `messages`/`conversations` for
   the analytics dashboards and the NLU/regression evaluation suites.

## Escalation path

The dialog manager escalates to a human on any of: low intent confidence after one
clarification attempt, repeated slot-filling failure, a negative sentiment streak, or an
explicit "speak to a human" / safety-concern intent (`dialog/policy.py`). Escalating creates
an `Escalation` row (`escalation_workflow.py` for its status state machine) and publishes a
`portal_feed` event over `WS /portal/live`, so a staff member sees it appear in
`pages/portal/Escalations.tsx` in real time without polling.

## Why two LLM providers

`llm/router.py` tries the primary provider (Groq) and fails over to the secondary (Gemini) on
a transient error, so a single provider outage doesn't take down the free-text-question path.
If neither is configured or both are down, deterministic flows (booking, reschedule, recall
check) still complete with zero degradation, and free-text questions escalate to a human
instead of failing silently -- both are exercised directly in
`backend/tests/test_scripted_conversations.py`'s provider-outage scenarios.

## Related documents

- [api.md](api.md) — REST API surface and where the generated OpenAPI docs live.
- [security.md](security.md) — static/dependency scan results and the RBAC model.
- [nlu-evaluation.md](nlu-evaluation.md) — intent classifier accuracy, confusion matrix, and
  escalation-gate precision/recall.
