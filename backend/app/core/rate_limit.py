"""slowapi rate limiting (Section 2.4): chat 20/min/session, login 10/min/IP."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
