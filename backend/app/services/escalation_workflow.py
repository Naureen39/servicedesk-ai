"""Escalation workflow (Section 5.3): status transitions open -> assigned -> in_progress ->
resolved | closed, and SLA breach detection for the portal.
"""

from __future__ import annotations

from datetime import UTC, datetime

STATUS_OPEN = "open"
STATUS_ASSIGNED = "assigned"
STATUS_IN_PROGRESS = "in_progress"
STATUS_RESOLVED = "resolved"
STATUS_CLOSED = "closed"

ALL_STATUSES = {STATUS_OPEN, STATUS_ASSIGNED, STATUS_IN_PROGRESS, STATUS_RESOLVED, STATUS_CLOSED}

# Section 5.3: "Statuses open -> assigned -> in_progress -> resolved | closed". A resolved
# escalation can be reopened to in_progress (a customer follow-up on a "resolved" issue is
# common); closed is terminal.
VALID_TRANSITIONS: dict[str, set[str]] = {
    STATUS_OPEN: {STATUS_ASSIGNED, STATUS_CLOSED},
    STATUS_ASSIGNED: {STATUS_IN_PROGRESS, STATUS_OPEN, STATUS_CLOSED},
    STATUS_IN_PROGRESS: {STATUS_RESOLVED, STATUS_CLOSED},
    STATUS_RESOLVED: {STATUS_CLOSED, STATUS_IN_PROGRESS},
    STATUS_CLOSED: set(),
}


class InvalidStatusTransitionError(Exception):
    pass


def validate_transition(current_status: str, new_status: str) -> None:
    if new_status not in ALL_STATUSES:
        raise InvalidStatusTransitionError(f"Unknown status: {new_status}")
    if new_status == current_status:
        return
    if new_status not in VALID_TRANSITIONS.get(current_status, set()):
        raise InvalidStatusTransitionError(f"Cannot transition escalation from {current_status!r} to {new_status!r}")


def is_sla_breached(status: str, sla_due_at: datetime | None) -> bool:
    if status in (STATUS_RESOLVED, STATUS_CLOSED):
        return False
    if sla_due_at is None:
        return False
    return datetime.now(UTC) > sla_due_at
