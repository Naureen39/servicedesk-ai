"""slowapi rate limiting (Section 2.4): chat 20/min/session, login 10/min/IP."""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# The limiter keys on remote IP, not session token, so a Locust load test run from a single
# machine (Phase 9: "100 concurrent chat users") would otherwise share one bucket and measure
# 429s instead of real endpoint latency. DISABLE_RATE_LIMIT is for that measurement only --
# never set in a deployed environment.
limiter = Limiter(key_func=get_remote_address, enabled=os.environ.get("DISABLE_RATE_LIMIT") != "1")
