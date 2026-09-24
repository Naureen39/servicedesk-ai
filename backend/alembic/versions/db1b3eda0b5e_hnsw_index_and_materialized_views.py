"""hnsw index and materialized views

Revision ID: db1b3eda0b5e
Revises: ec262437a8c3
Create Date: 2026-09-24 12:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "db1b3eda0b5e"
down_revision: str | None = "ec262437a8c3"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


MATVIEWS = {
    "mv_revenue_daily": """
        CREATE MATERIALIZED VIEW mv_revenue_daily AS
        SELECT
            location_id,
            date_trunc('day', closed_at)::date AS day,
            count(*) AS ro_count,
            sum(labor_amount) AS labor_revenue,
            sum(parts_amount) AS parts_revenue,
            sum(total_amount) AS total_revenue
        FROM repair_orders
        WHERE closed_at IS NOT NULL
        GROUP BY location_id, date_trunc('day', closed_at)::date
    """,
    "mv_revenue_monthly_by_service": """
        CREATE MATERIALIZED VIEW mv_revenue_monthly_by_service AS
        SELECT
            r.location_id,
            date_trunc('month', r.closed_at)::date AS month,
            l.service_code,
            count(*) AS line_count,
            sum(l.line_amount) AS revenue
        FROM ro_line_items l
        JOIN repair_orders r ON r.ro_id = l.ro_id
        WHERE r.closed_at IS NOT NULL
        GROUP BY r.location_id, date_trunc('month', r.closed_at)::date, l.service_code
    """,
    "mv_tech_productivity_weekly": """
        CREATE MATERIALIZED VIEW mv_tech_productivity_weekly AS
        SELECT
            technician_id,
            location_id,
            date_trunc('week', closed_at)::date AS week,
            count(*) AS ro_count,
            sum(labor_hours) AS labor_hours_billed,
            sum(total_amount) AS revenue
        FROM repair_orders
        WHERE closed_at IS NOT NULL AND technician_id IS NOT NULL
        GROUP BY technician_id, location_id, date_trunc('week', closed_at)::date
    """,
    "mv_bay_utilization_daily": """
        CREATE MATERIALIZED VIEW mv_bay_utilization_daily AS
        SELECT
            location_id,
            bay_number,
            date_trunc('day', scheduled_start)::date AS day,
            count(*) AS appointment_count,
            sum(extract(epoch FROM (scheduled_end - scheduled_start)) / 60.0) AS booked_minutes
        FROM appointments
        WHERE status IN ('completed', 'booked') AND bay_number IS NOT NULL
        GROUP BY location_id, bay_number, date_trunc('day', scheduled_start)::date
    """,
    "mv_assistant_kpis_daily": """
        CREATE MATERIALIZED VIEW mv_assistant_kpis_daily AS
        SELECT
            date_trunc('day', c.started_at)::date AS day,
            c.location_id,
            c.channel,
            count(*) AS conversation_count,
            sum(CASE WHEN c.contained THEN 1 ELSE 0 END) AS contained_count,
            sum(CASE WHEN c.escalated THEN 1 ELSE 0 END) AS escalated_count,
            avg((m.tokens_in + m.tokens_out)) FILTER (WHERE m.tokens_in IS NOT NULL) AS avg_tokens_per_message,
            avg(CASE WHEN m.cache_hit THEN 1.0 ELSE 0.0 END) AS cache_hit_rate
        FROM conversations c
        LEFT JOIN messages m ON m.conversation_id = c.conversation_id
        WHERE c.started_at IS NOT NULL
        GROUP BY date_trunc('day', c.started_at)::date, c.location_id, c.channel
    """,
}

# Each materialized view needs a unique index to support REFRESH ... CONCURRENTLY
# (APScheduler nightly refresh job, Section 2.1).
UNIQUE_INDEXES = {
    "mv_revenue_daily": ("uq_mv_revenue_daily", "(location_id, day)"),
    "mv_revenue_monthly_by_service": (
        "uq_mv_revenue_monthly_by_service",
        "(location_id, month, service_code)",
    ),
    "mv_tech_productivity_weekly": (
        "uq_mv_tech_productivity_weekly",
        "(technician_id, location_id, week)",
    ),
    "mv_bay_utilization_daily": (
        "uq_mv_bay_utilization_daily",
        "(location_id, bay_number, day)",
    ),
    "mv_assistant_kpis_daily": (
        "uq_mv_assistant_kpis_daily",
        "(day, location_id, channel)",
    ),
}


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_kb_chunks_embedding_hnsw ON kb_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_intent_examples_embedding_hnsw ON intent_examples "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_response_cache_embedding_hnsw ON response_cache "
        "USING hnsw (question_embedding vector_cosine_ops)"
    )

    for name, sql in MATVIEWS.items():
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {name}")
        op.execute(sql)
        index_name, columns = UNIQUE_INDEXES[name]
        op.execute(f"CREATE UNIQUE INDEX {index_name} ON {name} {columns}")


def downgrade() -> None:
    for name in MATVIEWS:
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {name} CASCADE")
    op.execute("DROP INDEX IF EXISTS ix_response_cache_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_intent_examples_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_embedding_hnsw")
