"""Phase 9 DoD: 100 concurrent simulated chat users, p95 < 400ms for non-LLM turns.

Booking is a fully deterministic dialog flow (0 LLM calls end to end -- see
backend/tests/test_scripted_conversations.py's BOOKING_SCRIPTS comment), so it's the
representative "non-LLM turn" workload: NLU intent/slot extraction, Postgres reads/writes,
and real availability computation, with no LLM round trip in the critical path.

Run against a real, already-running dev server:
    DISABLE_RATE_LIMIT=1 uvicorn app.main:app  (in one terminal)
    locust -f loadtest/locustfile.py --headless -u 100 -r 20 -t 2m --host http://localhost:8000

DISABLE_RATE_LIMIT is required: the chat endpoint's 20/min limit keys on remote IP (Section
2.4), and every simulated user in a Locust run shares this machine's one IP.
"""

from __future__ import annotations

import random

from locust import HttpUser, between, task

VEHICLES = ["2020 Toyota Camry", "2019 Honda Civic", "2021 Ford F-150", "2018 Toyota Corolla"]
SERVICES = ["an oil change", "a tire rotation", "brake pads", "a 60k service"]
DATES = ["next Tuesday", "tomorrow", "this Friday", "next Monday"]


class ChatUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        resp = self.client.post("/api/v1/chat/session", params={"channel": "chat"}, name="/chat/session")
        body = resp.json()
        self.session_token = body["session_token"]
        self.conversation_id = body["conversation_id"]

    def _send(self, text: str):
        return self.client.post(
            "/api/v1/chat/message",
            json={"conversation_id": self.conversation_id, "text": text},
            headers={"Authorization": f"Bearer {self.session_token}"},
            name="/chat/message (booking turn)",
        )

    @task
    def book_appointment(self) -> None:
        suffix = random.randint(1000, 9999)
        turns = [
            f"I need to book {random.choice(SERVICES)}",
            random.choice(VEHICLES),
            random.choice(DATES),
            "Load Test User",
            f"614-555-{suffix}",
            "1",
        ]
        for turn in turns:
            self._send(turn)
