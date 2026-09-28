# API overview

The full, generated API reference (every endpoint, request/response schema, and example) is
served directly from the running backend:

- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`
- Raw OpenAPI schema: `GET /openapi.json`

This document is a map of the API surface, not a duplicate of the generated reference.

## Authentication

- Public endpoints (chat, booking, recall check, contact form, etc.) use an anonymous session
  token issued by `POST /api/v1/chat/session` and passed as a bearer token; it is scoped to
  one `conversation_id`.
- Staff endpoints use a JWT access token from `POST /api/v1/auth/login` (plus
  `POST /api/v1/auth/mfa/verify` for roles with MFA enabled -- mandatory for `admin`),
  refreshed via `POST /api/v1/auth/refresh`. Every staff route additionally requires a
  specific permission, enforced by `require_permission()` and documented in
  `backend/app/core/permissions.py`'s role -> permission matrix; see
  `backend/tests/test_rbac_matrix.py` for the full, tested matrix of every protected
  endpoint against every role.

## Endpoint groups (`/api/v1/...`)

| Prefix | Purpose | Auth |
| --- | --- | --- |
| `/auth` | Login, MFA verify, refresh, logout, current user | Public login; bearer for the rest |
| `/chat` | Session issuance, message send, SSE stream, feedback | Anonymous session token |
| `/voice` (`WS /voice/session`) | Real-time voice: STT in, dialog turn, TTS out, barge-in | Anonymous session token |
| `/services`, `/locations`, `/vehicles/*`, `/nhtsa/*`, `/recalls`, `/availability` | Public reference data and live NHTSA lookups | None |
| `/appointments` (public: `POST`, `POST /verify`, `DELETE /by-reference/...`, `GET .../calendar.ics`) | Self-service booking, verify, cancel, add-to-calendar | Anonymous / reference code + phone |
| `/appointments` (staff: `GET`, `PATCH`, `DELETE /{id}`) | Staff appointment management, location-scoped | Bearer + `appointments:read`/`write` |
| `/conversations`, `/escalations` | Staff conversation history and escalation triage | Bearer + `conversations:read`, `escalations:read`/`write` |
| `WS /portal/live` | Real-time escalation feed for the staff portal | Bearer |
| `/analytics/*` | Revenue, operations, technician, recall, assistant KPIs; CSV export | Bearer + `analytics:read`/`export` |
| `/admin/*` | Users, roles, settings, knowledge base editor, audit log | Bearer + resource-specific permission (`users:manage`, `settings:manage`, `kb:read`/`write`, `audit:read`) |
| `/test-console` | Staff-only sandbox to test the assistant's replies without a real customer conversation | Bearer + `test_console:use` |
| `/contact`, `/complaints/summary` | Public contact form and complaint trend summary | None |

## Error format

Errors use RFC 7807 problem details (`type`, `title`, `status`, `detail`, `request_id`), raised
via `AppError` (`backend/app/core/exceptions.py`) and returned with the matching HTTP status
code -- see any `4xx`/`5xx` response in `/openapi.json` for the exact shape.

## Rate limiting

- Chat messages: 20/minute, keyed by client IP (`backend/app/core/rate_limit.py`).
- Login attempts: 10/minute, keyed by client IP.

`DISABLE_RATE_LIMIT=1` turns this off; it exists only for the Locust load test
(`backend/loadtest/locustfile.py`), never for a deployed environment.

## Related documents

- [architecture.md](architecture.md) — how a request flows through the dialog manager,
  scheduling engine, and LLM router.
- [security.md](security.md) — the RBAC model, scan results, and reviewed risk decisions.
