import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from synthetic_rules import (  # noqa: E402
    aro_trend,
    containment_rate,
    days_in_month,
    is_open_day,
    labor_rate_for_date,
    month_seasonality,
    no_show_probability,
    weekday_weight,
    yoy_growth_multiplier,
)


def test_month_seasonality_spring_and_fall_peak_over_december():
    assert month_seasonality(4) > month_seasonality(12)
    assert month_seasonality(10) > month_seasonality(12)


def test_month_seasonality_rejects_bad_input():
    with pytest.raises(ValueError):
        month_seasonality(13)


def test_weekday_weight_saturday_busiest_monday_second():
    assert weekday_weight(5) > weekday_weight(0)
    assert weekday_weight(0) > weekday_weight(1)


def test_weekday_weight_sunday_closed():
    assert weekday_weight(6) == 0.0


def test_yoy_growth_multiplier_one_year_matches_rate():
    result = yoy_growth_multiplier(2024, date(2025, 1, 1), annual_growth=0.08)
    assert result == pytest.approx(1.08, rel=1e-6)


def test_labor_rate_for_date_picks_latest_applicable():
    schedule = [(date(2024, 1, 1), 139.0), (date(2025, 1, 1), 145.0), (date(2026, 1, 1), 152.0)]
    assert labor_rate_for_date(date(2024, 6, 1), schedule) == 139.0
    assert labor_rate_for_date(date(2025, 6, 1), schedule) == 145.0
    assert labor_rate_for_date(date(2026, 6, 1), schedule) == 152.0
    assert labor_rate_for_date(date(2023, 1, 1), schedule) == 139.0


def test_no_show_probability_higher_when_booked_far_out():
    assert no_show_probability(20) > no_show_probability(5)


def test_is_open_day_sunday_and_holiday_closed():
    holidays = {date(2025, 12, 25)}
    assert is_open_day(date(2025, 12, 25), holidays) is False
    assert is_open_day(date(2025, 12, 21), holidays) is False  # a Sunday
    assert is_open_day(date(2025, 12, 22), holidays) is True


def test_aro_trend_increases_toward_end_of_window():
    start = date(2023, 10, 1)
    early = aro_trend(date(2023, 10, 1), start)
    late = aro_trend(date(2026, 9, 1), start)
    assert late > early
    assert early == pytest.approx(310.0, abs=1.0)


def test_containment_rate_ramps_up_and_caps():
    launch = date(2025, 9, 1)
    assert containment_rate(launch, launch) == pytest.approx(0.58)
    assert containment_rate(date(2026, 9, 1), launch) == pytest.approx(0.78)
    assert containment_rate(date(2030, 1, 1), launch) == pytest.approx(0.78)


def test_days_in_month():
    assert days_in_month(2024, 2) == 29
    assert days_in_month(2025, 2) == 28
