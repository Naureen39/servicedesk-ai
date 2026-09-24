"""Analytics endpoints (Section 2.5), reading from the Phase 2 materialized views so results
are real aggregates over the Phase 1 data, not mocked numbers. Drill-down, previous-period
comparison, and the full chart set are Phase 8; this phase proves the RBAC-gated, indexed
read path end to end for each named route.
"""

from __future__ import annotations

import csv
import io
from datetime import date

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


@router.get("/overview")
async def analytics_overview(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    location_id: int | None = Query(default=None),
    user: CurrentUser = Depends(require_permission(PERM_ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    sql = f"""
        SELECT sum(ro_count) AS ro_count, sum(total_revenue) AS total_revenue,
               sum(labor_revenue) AS labor_revenue, sum(parts_revenue) AS parts_revenue
        FROM mv_revenue_daily
        WHERE day BETWEEN :from_date AND :to_date
        {loc_clause}
    """
    rows = await _query_mv(db, sql, params)
    return rows[0] if rows else {}


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
    loc_clause, params = _date_and_location_params(from_, to, location_filter(user, location_id))
    if granularity == "month":
        sql = f"""
            SELECT location_id, service_code, month AS bucket, sum(revenue) AS revenue
            FROM mv_revenue_monthly_by_service
            WHERE month BETWEEN :from_date AND :to_date
            {loc_clause}
            GROUP BY location_id, service_code, month
            ORDER BY month
        """
    else:
        sql = f"""
            SELECT location_id, day AS bucket, total_revenue, ro_count
            FROM mv_revenue_daily
            WHERE day BETWEEN :from_date AND :to_date
            {loc_clause}
            ORDER BY day
        """
    rows = await _query_mv(db, sql, params)
    # `compare` (previous_period/previous_year overlay) is implemented in Phase 8 alongside the
    # rest of the dashboard's drill-down UI; the flag is accepted here for API stability.
    return {"granularity": granularity, "compare": compare, "rows": rows}


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
