"""Unit tests for the escalation status state machine and SLA breach detection
(Section 5.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services.escalation_workflow import (
    InvalidStatusTransitionError,
    is_sla_breached,
    validate_transition,
)


def test_valid_forward_transitions_are_accepted():
    validate_transition("open", "assigned")
    validate_transition("assigned", "in_progress")
    validate_transition("in_progress", "resolved")
    validate_transition("resolved", "closed")


def test_same_status_transition_is_a_no_op():
    validate_transition("open", "open")
    validate_transition("closed", "closed")


def test_resolved_can_be_reopened_to_in_progress():
    validate_transition("resolved", "in_progress")


def test_any_non_closed_status_can_be_closed():
    validate_transition("open", "closed")
    validate_transition("assigned", "closed")
    validate_transition("in_progress", "closed")


def test_closed_is_terminal():
    with pytest.raises(InvalidStatusTransitionError):
        validate_transition("closed", "open")
    with pytest.raises(InvalidStatusTransitionError):
        validate_transition("closed", "resolved")


def test_unknown_target_status_is_rejected():
    with pytest.raises(InvalidStatusTransitionError):
        validate_transition("open", "not-a-real-status")


def test_skipping_a_stage_is_rejected():
    with pytest.raises(InvalidStatusTransitionError):
        validate_transition("open", "in_progress")
    with pytest.raises(InvalidStatusTransitionError):
        validate_transition("open", "resolved")


def test_sla_not_breached_when_resolved_or_closed_even_if_overdue():
    overdue = datetime.now(UTC) - timedelta(days=1)
    assert is_sla_breached("resolved", overdue) is False
    assert is_sla_breached("closed", overdue) is False


def test_sla_not_breached_when_no_due_date_set():
    assert is_sla_breached("open", None) is False


def test_sla_breached_when_due_date_in_the_past():
    overdue = datetime.now(UTC) - timedelta(hours=1)
    assert is_sla_breached("open", overdue) is True
    assert is_sla_breached("in_progress", overdue) is True


def test_sla_not_breached_when_due_date_in_the_future():
    not_yet_due = datetime.now(UTC) + timedelta(hours=1)
    assert is_sla_breached("assigned", not_yet_due) is False
