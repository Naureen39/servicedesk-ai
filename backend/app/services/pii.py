"""PII redaction before any LLM call (Section 2.4).

Phone numbers, email addresses, and full VINs (keeping the last 6 characters) are replaced
with placeholders before a message is sent to an LLM provider; the response composer
(Phase 4) re-hydrates placeholders back into the final user-facing text using the returned
mapping. Names are handled by the dialog manager's slot-filling in Phase 4, since they require
NLU context this module does not have; this module only redacts text that can be found by
pattern alone.
"""

from __future__ import annotations

import re

_PHONE_RE = re.compile(r"(?<!\d)(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")


def redact_pii(text: str) -> tuple[str, dict[str, str]]:
    """Returns (redacted_text, placeholder_to_original) so the caller can re-hydrate later."""
    mapping: dict[str, str] = {}
    counter = {"phone": 0, "email": 0, "vin": 0}

    def _sub(pattern: re.Pattern[str], kind: str, keep_suffix: int = 0) -> None:
        nonlocal text

        def repl(match: re.Match[str]) -> str:
            original = match.group(0)
            if keep_suffix:
                # VINs are truncated, not placeholder-swapped: the last `keep_suffix`
                # characters are intentionally left visible to both the LLM and the end
                # user, so there is nothing to re-hydrate afterward.
                return f"...{original[-keep_suffix:]}"
            counter[kind] += 1
            placeholder = f"[{kind.upper()}_{counter[kind]}]"
            mapping[placeholder] = original
            return placeholder

        text = pattern.sub(repl, text)

    _sub(_EMAIL_RE, "email")
    _sub(_PHONE_RE, "phone")
    _sub(_VIN_RE, "vin", keep_suffix=6)

    return text, mapping


def rehydrate(text: str, mapping: dict[str, str]) -> str:
    for placeholder, original in mapping.items():
        text = text.replace(placeholder, original)
    return text
