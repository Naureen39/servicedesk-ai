"""Slot extraction (Section 4.1): regex for VIN, phone, reference code, year; rapidfuzz
matching of make/model against the vehicle catalog; dateparser for relative dates; service
type via catalog synonyms plus embedding similarity.
"""

from __future__ import annotations

import re
from datetime import datetime

from app.services.nlu import catalog_cache

VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
PHONE_RE = re.compile(r"(?<!\d)(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)")
REFERENCE_CODE_RE = re.compile(r"\bMRD[- ]?([A-Z0-9]{6})\b", re.IGNORECASE)
"""The hyphen is optional and a bare space also matches: Whisper transcribes a spoken
"em ar dee four eight two nine one three" as "MRD 482913" (no hyphen), which a strictly
hyphen-literal pattern would silently drop on the voice channel (Phase 6)."""
YEAR_MIN = 1990
_DIGIT_GROUP_COMMA_RE = re.compile(r"(?<=\d),(?=\d)")


def _strip_digit_commas(text: str) -> str:
    """A spoken phone number transcribed by Whisper comes back thousands-grouped
    ("6,145,550,101" instead of "614-555-0101"), which silently defeats phone extraction on
    the voice channel (Phase 6) since none of PHONE_RE's separators include a comma. Stripping
    commas that sit strictly between two digits undoes that formatting without touching commas
    used any other way."""
    return _DIGIT_GROUP_COMMA_RE.sub("", text)


def extract_vin(text: str) -> str | None:
    match = VIN_RE.search(text.upper())
    return match.group(0) if match else None


def extract_phone(text: str) -> str | None:
    match = PHONE_RE.search(_strip_digit_commas(text))
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"


def extract_phone_last4(text: str) -> str | None:
    """Section 5.2: reschedule/cancel verify by reference code plus last 4 phone digits.
    Accepts either a full phone number (takes its last 4 digits) or a bare 4-digit answer."""
    full_phone = extract_phone(text)
    if full_phone:
        return re.sub(r"\D", "", full_phone)[-4:]
    match = re.search(r"(?<!\d)\d{4}(?!\d)", _strip_digit_commas(text))
    return match.group(0) if match else None


def extract_reference_code(text: str) -> str | None:
    match = REFERENCE_CODE_RE.search(text.upper())
    return f"MRD-{match.group(1)}" if match else None


def extract_year(text: str, current_year: int | None = None) -> int | None:
    current_year = current_year or datetime.now().year
    for match in re.finditer(r"\b(19|20)\d{2}\b", text):
        year = int(match.group(0))
        if YEAR_MIN <= year <= current_year + 1:
            return year
    return None


_NEXT_THIS_WEEKDAY_RE = re.compile(
    r"\b(?:next|this)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE
)


def extract_date(text: str, base: datetime | None = None) -> datetime | None:
    import dateparser

    # dateparser 1.4.x does not resolve "next Tuesday" / "this Friday" (only bare weekday
    # names and phrases like "next week"); stripping the leading "next"/"this" and handing it
    # the bare weekday name gets the same answer, since dateparser already treats a bare
    # weekday name as the next upcoming occurrence.
    normalized = _NEXT_THIS_WEEKDAY_RE.sub(lambda m: m.group(1), text)

    return dateparser.parse(
        normalized,
        languages=["en"],
        # Without `languages`, dateparser tries every locale's parser on every call (this
        # project is English-only), which measured at ~1-2s per call on plain non-date text
        # like a customer's name -- the dominant cost in slot extraction and, once voice's
        # tight latency budget (Phase 6 DoD) made it visible, the main thing blowing it. This
        # was never wrong, just slow enough to be a genuine performance bug.
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": base or datetime.now(),
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )


def extract_make_model(text: str, score_cutoff: float = 80.0) -> tuple[str | None, str | None]:
    """Fuzzy-matches make and model against the vehicle catalog cache (Section 4.1). The
    catalog must be warmed with `catalog_cache.refresh(db)` first; returns (None, None) if it
    hasn't been (never guesses against an empty/stale reference list)."""
    from rapidfuzz import fuzz, process

    if not catalog_cache.is_loaded():
        return None, None

    words = text.split()
    ngrams = set(words)
    for n in (2, 3):
        ngrams.update(" ".join(words[i : i + n]) for i in range(len(words) - n + 1))

    make_match = process.extractOne(text, catalog_cache.get_makes(), scorer=fuzz.partial_ratio, score_cutoff=score_cutoff)
    make = make_match[0] if make_match else None

    candidate_models = catalog_cache.get_models(make)
    best_model = None
    best_score = 0.0
    for gram in ngrams:
        if len(gram) < 2:
            continue
        result = process.extractOne(gram, candidate_models, scorer=fuzz.WRatio, score_cutoff=score_cutoff)
        if result and result[1] > best_score:
            best_model, best_score = result[0], result[1]

    return make, best_model


def extract_service_type(text: str, similarity_cutoff: float = 0.45) -> str | None:
    """Matches free text like "I need an oil change" to a service_catalog code, first via
    exact/fuzzy name matching (fast, zero embedding calls), falling back to embedding
    similarity against each service's name+category (Section 4.1: "catalog synonyms plus
    embedding similarity")."""
    from rapidfuzz import fuzz, process

    rows = catalog_cache.get_service_rows()
    if not rows:
        return None

    names = [row["name"] for row in rows]
    fuzzy = process.extractOne(text, names, scorer=fuzz.partial_ratio, score_cutoff=70.0)
    if fuzzy:
        return rows[names.index(fuzzy[0])]["code"]

    from app.services.embeddings import embed_passages

    query_vec = embed_passages([text])[0]
    service_vecs = catalog_cache.get_or_compute_service_embeddings()

    best_code, best_sim = None, 0.0
    for row, vec in zip(rows, service_vecs, strict=True):
        sim = sum(a * b for a, b in zip(query_vec, vec, strict=True))  # both normalized -> cosine
        if sim > best_sim:
            best_code, best_sim = row["code"], sim

    return best_code if best_sim >= similarity_cutoff else None


def extract_all(text: str) -> dict:
    make, model = extract_make_model(text)
    return {
        "vin": extract_vin(text),
        "phone": extract_phone(text),
        "phone_last4": extract_phone_last4(text),
        "reference_code": extract_reference_code(text),
        "year": extract_year(text),
        "date": extract_date(text),
        "make": make,
        "model": model,
        "service_code": extract_service_type(text),
    }
