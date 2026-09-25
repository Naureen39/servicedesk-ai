"""Voice-specific response formatting (Phase 6 item 4): converts the same response text the
chat channel would show into TTS-friendly spoken form -- "twenty nineteen" instead of "2019",
"nine thirty a m" instead of "09:30 AM" -- and a separate digit-by-digit reader for read-back
confirmation of critical values (item 7).
"""

from __future__ import annotations

import re

from num2words import num2words

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\s*(AM|PM)\b", re.IGNORECASE)


def spoken_year(year: int) -> str:
    if 2000 <= year <= 2009:
        if year == 2000:
            return "two thousand"
        return f"two thousand {num2words(year - 2000)}".replace("-", " ")
    century, remainder = divmod(year, 100)
    century_word = num2words(century)
    if remainder == 0:
        return f"{century_word} hundred"
    return f"{century_word} {num2words(remainder)}".replace("-", " ")


def spoken_clock(hour: int, minute: int, meridiem: str) -> str:
    hour_word = num2words(hour)
    if minute == 0:
        minute_word = "o'clock"
    elif minute < 10:
        minute_word = f"oh {num2words(minute)}"
    else:
        minute_word = num2words(minute)
    meridiem_word = "a m" if meridiem.upper() == "AM" else "p m"
    return f"{hour_word} {minute_word} {meridiem_word}".replace("-", " ")


def spoken_digits(value: str) -> str:
    """Reads a code digit by digit -- used for read-back confirmation, e.g. phone last 4
    ("4 5 1 2") or a confirmation reference code."""
    return " ".join(ch for ch in value if ch.isdigit())


def _replace_year(match: re.Match) -> str:
    return spoken_year(int(match.group(0)))


def _replace_time(match: re.Match) -> str:
    hour, minute, meridiem = int(match.group(1)), int(match.group(2)), match.group(3)
    return spoken_clock(hour, minute, meridiem)


def spokenize(text: str) -> str:
    text = _TIME_RE.sub(_replace_time, text)
    text = _YEAR_RE.sub(_replace_year, text)
    return text
