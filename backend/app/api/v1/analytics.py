"""Analytics endpoints (Section 2.5), reading from the Phase 2 materialized views so results
are real aggregates over the Phase 1 data, not mocked numbers. Drill-down, previous-period
comparison, and the full chart set are Phase 8; this phase proves the RBAC-gated, indexed
read path end to end for each named route.
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import PERM_ANALYTICS_EXPORT, PERM_ANALYTICS_READ
from app.db.base import get_db

from .deps import CurrentUser, location_filter, require_permission

router = APIRouter(prefix="/analytics", tags=["analytics"])


async def _query_mv(db: AsyncSession, sql: str, params: dict) -> list[dict]:
    result = await db.execute(text(sql), params)
    return [dict(row._mapping) for row in result.all()]


def _date_and_location_params(from_: date | None, to: date | None, location_id: int | None) -> tuple[str, dict]:
    """Returns (location_clause, params). `location_clause` is either "" or
    "AND location_id = :location_id" -- built conditionally rather than an
    "(:location_id IS NULL OR ...)" SQL pattern, since asyncpg cannot infer the parameter's
    type when the same placeholder is compared to NULL and to a column in one prepared
    statement."""
    params = {
        "from_date": from_ or date(2000, 1, 1),
        "to_date": to or date(2100, 1, 1),
    }
    if location_id is None:
        return "", params
    params["location_id"] = location_id
    return "AND location_id = :location_id", params


async def _revenue_kpis(db: AsyncSession, loc_clause: str, params: dict) -> dict:
    sql = f"""
        SELECT sum(ro_count) AS ro_count, sum(total_revenue) AS total_revenue,
               sum(labor_revenue) AS labor_revenue, sum(parts_revenue) AS parts_revenue
        FROM mv_revenue_daily
        WHERE day BETWEEN :from_date AND :to_date
        {loc_clause}
    """
    rows = await _query_mv(db, sql, params)
    return rows[0] if rows and rows[0]["ro_count"] else {"ro_count": 0, "total_revenue": 0, "labor_revenue": 0, "parts_revenue": 0}


@router.get("/overview")
async def analytics_overview(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Section 8.3 Executive Overview: "KPI cards with sparkline and delta vs previous
    period" -- the previous period is the same-length window immediately before `from_`."""
    scoped_location_id = location_filter(user, location_id)
    loc_clause, params = _date_and_location_params(from_, to, scoped_location_id)
    current = await _revenue_kpis(db, loc_clause, params)

    prev_kpis: dict = {}
    if from_ is not None and to is not None:
        span_days = (to - from_).days + 1
        prev_from = from_ - timedelta(days=span_days)
        prev_to = from_ - timedelta(days=1)
        prev_loc_clause, prev_params = _date_and_location_params(prev_from, prev_to, scoped_location_id)
        prev_kpis = await _revenue_kpis(db, prev_loc_clause, prev_params)

    csat_loc = "AND l.location_id = :location_id" if scoped_location_id is not None else ""
    csat_params = dict(params)
    csat_sql = f"""
        SELECT avg(s.score) AS avg_csat, avg(s.wait_time_minutes) AS avg_wait_minutes,
               avg(s.promise_time_minutes) AS avg_promise_minutes
        FROM csat_surveys s
        JOIN repair_orders r ON r.ro_id = s.ro_id
        JOIN locations l ON l.location_id = r.location_id
        WHERE r.closed_at::date BETWEEN :from_date AND :to_date {csat_loc}
    """
    csat_rows = await _query_mv(db, csat_sql, csat_params)

    bay_sql = f"""
        SELECT sum(booked_minutes) AS booked_minutes, count(DISTINCT (location_id, bay_number)) AS bay_count,
               count(DISTINCT day) AS day_count
        FROM mv_bay_utilization_daily
        WHERE day BETWEEN :from_date AND :to_date
        {loc_clause}
    """
    bay_rows = await _query_mv(db, bay_sql, params)

    assistant_sql = f"""
        SELECT sum(conversation_count) AS conversation_count, sum(contained_count) AS contained_count
        FROM mv_assistant_kpis_daily
        WHERE day BETWEEN :from_date AND :to_date
        {loc_clause}
    """
    assistant_rows = await _query_mv(db, assistant_sql, params)
    assistant = assistant_rows[0] if assistant_rows else {}
    containment_rate = None
    if assistant.get("conversation_count"):
        containment_rate = float(assistant["contained_count"] or 0) / float(assistant["conversation_count"])

    bay = bay_rows[0] if bay_rows else {}
    bay_utilization_pct = None
    if bay.get("bay_count") and bay.get("day_count"):
        available_minutes = float(bay["bay_count"]) * float(bay["day_count"]) * 24 * 60
        bay_utilization_pct = (float(bay["booked_minutes"] or 0) / available_minutes) if available_minutes else None

    ro_count = float(current.get("ro_count") or 0)
    total_revenue = float(current.get("total_revenue") or 0)
    return {
        "current": current,
        "previous": prev_kpis,
        "aro": (total_revenue / ro_count) if ro_count else None,
        "effective_labor_rate": (
            float(current.get("labor_revenue") or 0) / float(current.get("ro_count") or 1) if current.get("ro_count") else None
        ),
        "bay_utilization_pct": bay_utilization_pct,
        "csat": (csat_rows[0] if csat_rows else {}),
        "assistant_containment_rate": containment_rate,
    }


def _revenue_sql(granularity: str, loc_clause: str) -> str:
    if granularity == "month":
        return f"""
            SELECT location_id, service_code, month AS bucket, sum(revenue) AS revenue
            FROM mv_revenue_monthly_by_service
            WHERE month BETWEEN :from_date AND :to_date
            {loc_clause}
            GROUP BY location_id, service_code, month
            ORDER BY month
        """
    return f"""
        SELECT location_id, day AS bucket, total_revenue, ro_count
        FROM mv_revenue_daily
        WHERE day BETWEEN :from_date AND :to_date
        {loc_clause}
        ORDER BY day
    """


@router.get("/revenue")
async def analytics_revenue(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    granularity: str = Query(default="day", pattern="^(day|month)$"),
    compare: str | None = Query(default=None, pattern="^(previous_period|previous_year)$"),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    scoped_location_id = location_filter(user, location_id)
    loc_clause, params = _date_and_location_params(from_, to, scoped_location_id)
    rows = await _query_mv(db, _revenue_sql(granularity, loc_clause), params)

    compare_rows: list[dict] = []
    if compare and from_ is not None and to is not None:
        if compare == "previous_year":
            prev_from, prev_to = from_.replace(year=from_.year - 1), to.replace(year=to.year - 1)
        else:
            span_days = (to - from_).days + 1
            prev_from, prev_to = from_ - timedelta(days=span_days), from_ - timedelta(days=1)
        prev_loc_clause, prev_params = _date_and_location_params(prev_from, prev_to, scoped_location_id)
        compare_rows = await _query_mv(db, _revenue_sql(granularity, prev_loc_clause), prev_params)

    return {"granularity": granularity, "compare": compare, "rows": rows, "compare_rows": compare_rows}


@router.get("/revenue/top-services")
async def analytics_top_services(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    limit: int = Query(default=10, le=50),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    params["limit"] = limit
    sql = f"""
        SELECT service_code, sum(revenue) AS revenue, sum(line_count) AS line_count
        FROM mv_revenue_monthly_by_service
        WHERE month BETWEEN :from_date AND :to_date
        {loc_clause}
        GROUP BY service_code
        ORDER BY revenue DESC NULLS LAST
        LIMIT :limit
    """
    rows = await _query_mv(db, sql, params)
    return {"rows": rows}


@router.get("/revenue/by-pay-type")
async def analytics_revenue_by_pay_type(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Section 8.3 Executive Overview: "revenue by pay type stacked area"."""
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    sql = f"""
        SELECT closed_at::date AS day, pay_type, sum(total_amount) AS revenue
        FROM repair_orders
        WHERE closed_at::date BETWEEN :from_date AND :to_date
        {loc_clause}
        GROUP BY closed_at::date, pay_type
        ORDER BY day
    """
    rows = await _query_mv(db, sql, params)
    return {"rows": rows}


@router.get("/revenue/by-location")
async def analytics_revenue_by_location(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Section 8.3 Executive Overview: "revenue by location bar" -- unfiltered by
    `location_id` on purpose (that's the axis being compared); still honors a
    service_advisor's own location scoping."""
    scoped_location_id = location_filter(user, None)
    loc_clause, params = _date_and_location_params(from_, to, scoped_location_id)
    sql = f"""
        SELECT location_id, sum(total_revenue) AS revenue
        FROM mv_revenue_daily
        WHERE day BETWEEN :from_date AND :to_date
        {loc_clause}
        GROUP BY location_id
        ORDER BY revenue DESC
    """
    rows = await _query_mv(db, sql, params)
    return {"rows": rows}


@router.get("/revenue/by-category")
async def analytics_revenue_by_category(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Section 8.3 Revenue Analytics: "revenue by service category treemap"."""
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    sql = f"""
        SELECT sc.category, sum(m.revenue) AS revenue
        FROM mv_revenue_monthly_by_service m
        JOIN service_catalog sc ON sc.code = m.service_code
        WHERE m.month BETWEEN :from_date AND :to_date
        {loc_clause}
        GROUP BY sc.category
        ORDER BY revenue DESC
    """
    rows = await _query_mv(db, sql, params)
    return {"rows": rows}


@router.get("/revenue/aro-distribution")
async def analytics_aro_distribution(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Section 8.3 Revenue Analytics: "ARO distribution histogram" -- real per-repair-order
    total buckets, not derived from the daily average."""
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    sql = f"""
        SELECT width_bucket(total_amount, 0, 2000, 20) AS bucket, count(*) AS count
        FROM repair_orders
        WHERE closed_at::date BETWEEN :from_date AND :to_date AND total_amount IS NOT NULL
        {loc_clause}
        GROUP BY bucket
        ORDER BY bucket
    """
    rows = await _query_mv(db, sql, params)
    return {"rows": rows}


@router.get("/operations")
async def analytics_operations(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    sql = f"""
        SELECT location_id, bay_number, day, appointment_count, booked_minutes
        FROM mv_bay_utilization_daily
        WHERE day BETWEEN :from_date AND :to_date
        {loc_clause}
        ORDER BY day
    """
    rows = await _query_mv(db, sql, params)
    return {"rows": rows}


@router.get("/operations/funnel")
async def analytics_operations_funnel(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Section 8.3 Service Operations: "appointment funnel (booked, arrived, completed,
    invoiced)" and "no-show and cancellation trend". Honest note: this dataset never tracks a
    separate "arrived" timestamp on an appointment (no check-in event exists), so the funnel
    below is booked -> completed -> invoiced (a real repair order exists) plus the two loss
    stages (no_show, cancelled) it actually has data for, rather than inventing an "arrived"
    count that has no backing column."""
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    funnel_sql = f"""
        SELECT status, count(*) AS count
        FROM appointments
        WHERE scheduled_start::date BETWEEN :from_date AND :to_date
        {loc_clause}
        GROUP BY status
    """
    funnel_rows = await _query_mv(db, funnel_sql, params)

    trend_sql = f"""
        SELECT scheduled_start::date AS day,
               count(*) FILTER (WHERE status = 'no_show') AS no_show_count,
               count(*) FILTER (WHERE status = 'cancelled') AS cancelled_count,
               count(*) AS total_count
        FROM appointments
        WHERE scheduled_start::date BETWEEN :from_date AND :to_date
        {loc_clause}
        GROUP BY scheduled_start::date
        ORDER BY day
    """
    trend_rows = await _query_mv(db, trend_sql, params)

    invoiced_sql = f"""
        SELECT count(DISTINCT a.appointment_id) AS invoiced_count
        FROM appointments a
        JOIN repair_orders r ON r.appointment_id = a.appointment_id
        WHERE a.scheduled_start::date BETWEEN :from_date AND :to_date
        {loc_clause.replace("location_id", "a.location_id")}
    """
    invoiced_rows = await _query_mv(db, invoiced_sql, params)

    return {
        "by_status": funnel_rows,
        "invoiced_count": invoiced_rows[0]["invoiced_count"] if invoiced_rows else 0,
        "trend": trend_rows,
    }


@router.get("/operations/heatmap")
async def analytics_operations_heatmap(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Section 8.3 Service Operations: "appointments by weekday and hour heatmap"."""
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    sql = f"""
        SELECT extract(dow FROM scheduled_start)::int AS weekday, extract(hour FROM scheduled_start)::int AS hour,
               count(*) AS count
        FROM appointments
        WHERE scheduled_start::date BETWEEN :from_date AND :to_date
        {loc_clause}
        GROUP BY weekday, hour
    """
    rows = await _query_mv(db, sql, params)
    return {"rows": rows}


@router.get("/operations/wait-vs-promise")
async def analytics_operations_wait_vs_promise(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Section 8.3 Service Operations: "average wait vs promise time" -- real CSAT-survey
    data (the only place actual wait/promise minutes are recorded in this dataset)."""
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    sql = f"""
        SELECT r.closed_at::date AS day, avg(s.wait_time_minutes) AS avg_wait, avg(s.promise_time_minutes) AS avg_promise
        FROM csat_surveys s
        JOIN repair_orders r ON r.ro_id = s.ro_id
        WHERE r.closed_at::date BETWEEN :from_date AND :to_date
        {loc_clause}
        GROUP BY r.closed_at::date
        ORDER BY day
    """
    rows = await _query_mv(db, sql, params)
    return {"rows": rows}


@router.get("/technicians")
async def analytics_technicians(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    sql = f"""
        SELECT technician_id, location_id, week, ro_count, labor_hours_billed, revenue
        FROM mv_tech_productivity_weekly
        WHERE week BETWEEN :from_date AND :to_date
        {loc_clause}
        ORDER BY week
    """
    rows = await _query_mv(db, sql, params)
    return {"rows": rows}


@router.get("/assistant")
async def analytics_assistant(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    sql = f"""
        SELECT day, location_id, channel, conversation_count, contained_count,
               escalated_count, avg_tokens_per_message, cache_hit_rate
        FROM mv_assistant_kpis_daily
        WHERE day BETWEEN :from_date AND :to_date
        {loc_clause}
        ORDER BY day
    """
    rows = await _query_mv(db, sql, params)
    return {"rows": rows}


@router.get("/assistant/summary")
async def analytics_assistant_summary(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Section 8.3 Assistant Performance: intent distribution, confidence histogram, bookings
    and revenue attributed to the assistant, average turns to booking, provider split, and
    estimated advisor hours saved (contained conversations x 4 min, per the plan's own
    formula)."""
    scoped_location_id = location_filter(user, location_id)
    loc_clause, params = _date_and_location_params(from_, to, scoped_location_id)

    intent_sql = f"""
        SELECT m.intent, count(*) AS count
        FROM messages m
        JOIN conversations c ON c.conversation_id = m.conversation_id
        WHERE m.sender = 'assistant' AND m.intent IS NOT NULL
          AND c.started_at::date BETWEEN :from_date AND :to_date
          {loc_clause.replace("location_id", "c.location_id")}
        GROUP BY m.intent
        ORDER BY count DESC
    """
    intent_rows = await _query_mv(db, intent_sql, params)

    confidence_sql = f"""
        SELECT width_bucket(m.confidence, 0, 1, 10) AS bucket, count(*) AS count
        FROM messages m
        JOIN conversations c ON c.conversation_id = m.conversation_id
        WHERE m.sender = 'assistant' AND m.confidence IS NOT NULL
          AND c.started_at::date BETWEEN :from_date AND :to_date
          {loc_clause.replace("location_id", "c.location_id")}
        GROUP BY bucket
        ORDER BY bucket
    """
    confidence_rows = await _query_mv(db, confidence_sql, params)

    provider_sql = f"""
        SELECT m.provider, count(*) AS count
        FROM messages m
        JOIN conversations c ON c.conversation_id = m.conversation_id
        WHERE m.provider IS NOT NULL
          AND c.started_at::date BETWEEN :from_date AND :to_date
          {loc_clause.replace("location_id", "c.location_id")}
        GROUP BY m.provider
    """
    provider_rows = await _query_mv(db, provider_sql, params)

    attributed_sql = f"""
        SELECT count(DISTINCT r.ro_id) AS ro_count, sum(r.total_amount) AS revenue
        FROM repair_orders r
        JOIN appointments a ON a.appointment_id = r.appointment_id
        WHERE a.channel_created IN ('chat', 'voice')
          AND a.scheduled_start::date BETWEEN :from_date AND :to_date
          {loc_clause.replace("location_id", "a.location_id")}
    """
    attributed_rows = await _query_mv(db, attributed_sql, params)

    turns_sql = f"""
        SELECT avg((c.state->>'turn_count')::int) AS avg_turns_to_booking
        FROM conversations c
        WHERE c.resulting_appointment_id IS NOT NULL
          AND c.started_at::date BETWEEN :from_date AND :to_date
          {loc_clause}
    """
    turns_rows = await _query_mv(db, turns_sql, params)

    contained_sql = f"""
        SELECT count(*) FILTER (WHERE c.contained) AS contained_count
        FROM conversations c
        WHERE c.started_at::date BETWEEN :from_date AND :to_date
        {loc_clause}
    """
    contained_rows = await _query_mv(db, contained_sql, params)
    contained_count = (contained_rows[0]["contained_count"] if contained_rows else 0) or 0

    return {
        "intent_distribution": intent_rows,
        "confidence_histogram": confidence_rows,
        "provider_split": provider_rows,
        "assistant_attributed": attributed_rows[0] if attributed_rows else {},
        "avg_turns_to_booking": turns_rows[0]["avg_turns_to_booking"] if turns_rows else None,
        "estimated_advisor_hours_saved": round(contained_count * 4 / 60, 1),
    }


@router.get("/recalls")
async def analytics_recalls(
    make: str | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    make_clause = "AND make = :make" if make else ""
    sql = f"""
        SELECT make, model, model_year, count(*) AS campaign_count
        FROM recall_campaigns
        WHERE true {make_clause}
        GROUP BY make, model, model_year
        ORDER BY campaign_count DESC
        LIMIT 50
    """
    params = {"make": make.upper()} if make else {}
    rows = await _query_mv(db, sql, params)
    return {"rows": rows}


@router.get("/recalls/customer-impact")
async def analytics_recalls_customer_impact(
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Section 8.3 Recall and Safety Insights: "recall campaigns affecting the customer base
    (count of customer vehicles per open campaign) with an export list for outreach" --
    real join between the customer base's actual vehicles and open recall campaigns by
    year/make/model."""
    sql = """
        SELECT rc.campaign_number, rc.make, rc.model, rc.model_year, rc.component,
               count(DISTINCT v.vehicle_id) AS affected_vehicle_count
        FROM recall_campaigns rc
        JOIN vehicles v ON v.make = rc.make AND v.model = rc.model AND v.year = rc.model_year
        GROUP BY rc.campaign_number, rc.make, rc.model, rc.model_year, rc.component
        HAVING count(DISTINCT v.vehicle_id) > 0
        ORDER BY affected_vehicle_count DESC
        LIMIT 50
    """
    rows = await _query_mv(db, sql, {})
    return {"rows": rows}


@router.get("/recalls/customer-impact/export.csv")
async def analytics_recalls_customer_impact_export(
    campaign_number: str = Query(...),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_EXPORT)),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Outreach export list: real customers whose real vehicle matches a specific open
    campaign."""
    sql = """
        SELECT c.customer_id, c.first_name, c.last_name, v.vehicle_id, v.year, v.make, v.model, v.vin
        FROM recall_campaigns rc
        JOIN vehicles v ON v.make = rc.make AND v.model = rc.model AND v.year = rc.model_year
        JOIN customers c ON c.customer_id = v.customer_id
        WHERE rc.campaign_number = :campaign_number
        ORDER BY c.last_name, c.first_name
    """
    rows = await _query_mv(db, sql, {"campaign_number": campaign_number})

    buf = io.StringIO()
    fieldnames = ["customer_id", "first_name", "last_name", "vehicle_id", "year", "make", "model", "vin"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=recall_{campaign_number}_outreach.csv"},
    )


@router.get("/export.csv")
async def analytics_export_csv(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_EXPORT)),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    sql = f"""
        SELECT location_id, day, ro_count, labor_revenue, parts_revenue, total_revenue
        FROM mv_revenue_daily
        WHERE day BETWEEN :from_date AND :to_date
        {loc_clause}
        ORDER BY day
    """
    rows = await _query_mv(db, sql, params)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["location_id", "day", "ro_count", "labor_revenue", "parts_revenue", "total_revenue"])
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=revenue_export.csv"},
    )
