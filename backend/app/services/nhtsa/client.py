"""Low-level NHTSA HTTP client (Section 5.1): async httpx, 10s timeout, 3 retries with
exponential backoff, 500ms spacing between calls (a single process-wide throttle, since NHTSA
has no documented per-key rate limit but the plan asks for gentle, deliberate pacing)."""

from __future__ import annotations

import asyncio
import time

import httpx

TIMEOUT_S = 10.0
MAX_RETRIES = 3
BACKOFF_BASE_S = 1.0
MIN_SPACING_S = 0.5

_last_call_monotonic = 0.0
_spacing_lock = asyncio.Lock()


class NHTSAClientError(Exception):
    pass


async def _throttle() -> None:
    global _last_call_monotonic
    async with _spacing_lock:
        elapsed = time.monotonic() - _last_call_monotonic
        if elapsed < MIN_SPACING_S:
            await asyncio.sleep(MIN_SPACING_S - elapsed)
        _last_call_monotonic = time.monotonic()


async def get_json(url: str, params: dict | None = None) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        await _throttle()
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                await asyncio.sleep(BACKOFF_BASE_S * (2 ** (attempt - 1)))
    raise NHTSAClientError(f"NHTSA request to {url} failed after {MAX_RETRIES} attempts: {last_error}") from last_error
