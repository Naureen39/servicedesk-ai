"""Pure, unit-testable rule functions used by generate_synthetic.py.

Kept separate from the generation driver so each business rule from PROJECT_PLAN Section 4.4
can be tested in isolation without spinning up the full generator.
"""

from __future__ import annotations

import calendar
from datetime import date

# Month (1-12) -> seasonal multiplier. Spring and fall peaks, December dip.
MONTH_SEASONALITY = {
    1: 0.92, 2: 0.90, 3: 1.10, 4: 1.15, 5: 1.18,
    6: 1.05, 7: 1.00, 8: 0.98, 9: 1.08, 10: 1.12,
    11: 1.10, 12: 0.80,
}

# Weekday (Mon=0 .. Sun=6) -> relative volume weight. Sunday is closed everywhere (weight 0).
WEEKDAY_WEIGHT = {
    0: 1.15,  # Monday: second busiest
    1: 0.95,
    2: 0.95,
    3: 0.95,
    4: 1.00,
    5: 1.35,  # Saturday: busiest per open hour
    6: 0.0,
}

SATURDAY_CAPACITY_CAP = 0.90


def month_seasonality(month: int) -> float:
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1-12, got {month}")
    return MONTH_SEASONALITY[month]


def weekday_weight(weekday: int) -> float:
    if not 0 <= weekday <= 6:
        raise ValueError(f"weekday must be 0-6, got {weekday}")
    return WEEKDAY_WEIGHT[weekday]


def yoy_growth_multiplier(base_year: int, target_date: date, annual_growth: float = 0.08) -> float:
    """Compound annual RO growth of ~7-9%% (default 8%%) relative to `base_year`-01-01."""
    years_elapsed = (target_date.year - base_year) + (target_date.month - 1) / 12.0
    return (1.0 + annual_growth) ** years_elapsed


def labor_rate_for_date(target_date: date, rate_schedule: list[tuple[date, float]]) -> float:
    """rate_schedule: list of (effective_date, rate) sorted ascending. Returns rate in effect."""
    applicable = [r for eff, r in rate_schedule if eff <= target_date]
    if not applicable:
        return rate_schedule[0][1]
    return applicable[-1]


def no_show_probability(days_booked_ahead: int, base_rate: float = 0.06, far_out_rate: float = 0.09) -> float:
    """No-show rate is higher for bookings made more than 14 days out."""
    return far_out_rate if days_booked_ahead > 14 else base_rate


def is_open_day(target_date: date, holidays: set[date]) -> bool:
    if target_date.weekday() == 6:  # Sunday
        return False
    if target_date in holidays:
        return False
    return True


def aro_trend(target_date: date, start_date: date, start_aro: float = 310.0, end_aro: float = 365.0,
              window_months: int = 36) -> float:
    """Linear ARO trend from `start_aro` to `end_aro` across the generation window."""
    months_elapsed = (target_date.year - start_date.year) * 12 + (target_date.month - start_date.month)
    fraction = min(1.0, max(0.0, months_elapsed / max(1, window_months - 1)))
    return start_aro + fraction * (end_aro - start_aro)


def containment_rate(target_date: date, launch_date: date, start_rate: float = 0.58, end_rate: float = 0.78,
                      ramp_months: int = 12) -> float:
    """Assistant containment ramps from `start_rate` to `end_rate` over `ramp_months`."""
    months_elapsed = (target_date.year - launch_date.year) * 12 + (target_date.month - launch_date.month)
    fraction = min(1.0, max(0.0, months_elapsed / ramp_months))
    return start_rate + fraction * (end_rate - start_rate)


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]
