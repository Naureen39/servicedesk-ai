"""Regression tests for two real bugs found while building Phase 6's voice pipeline against a
real, tight per-turn latency budget: `extract_date`'s missing `languages=["en"]` (dateparser
tries every locale's parser without it, ~1-2s per call on plain non-date text) and
`extract_phone`/`extract_phone_last4` not handling Whisper's comma-thousands-grouped digit
transcriptions ("6,145,550,101" for a spoken phone number).
"""

from __future__ import annotations

import time

from app.services.nlu.slots import extract_date, extract_phone, extract_phone_last4, extract_reference_code


def test_extract_date_is_fast_on_non_date_text():
    t0 = time.monotonic()
    result = extract_date("Alicia Gomez")
    elapsed = time.monotonic() - t0
    assert result is None
    assert elapsed < 0.5, f"extract_date took {elapsed:.3f}s on plain text (expected well under 0.5s)"


def test_extract_date_still_resolves_relative_weekdays():
    assert extract_date("next Tuesday") is not None
    assert extract_date("this Friday") is not None
    assert extract_date("tomorrow") is not None


def test_extract_phone_handles_whisper_comma_grouped_digits():
    assert extract_phone("6,145,550,101.") == "614-555-0101"
    assert extract_phone("My number is 614-555-0101") == "614-555-0101"


def test_extract_phone_last4_handles_whisper_comma_grouped_digits():
    assert extract_phone_last4("6,145,550,101.") == "0101"
    assert extract_phone_last4("it's 4512") == "4512"


def test_extract_reference_code_handles_whisper_dropping_the_hyphen():
    """Whisper transcribes a spoken reference code as "MRD 482913" (space, no hyphen)."""
    assert extract_reference_code("My reference code is MRD 482913.") == "MRD-482913"
    assert extract_reference_code("MRD-482913") == "MRD-482913"
