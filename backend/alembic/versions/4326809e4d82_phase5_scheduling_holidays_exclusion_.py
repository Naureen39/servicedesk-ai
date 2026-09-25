"""phase5 scheduling: holidays, exclusion constraints, parts availability

Revision ID: 4326809e4d82
Revises: f5dc1737eea9
Create Date: 2026-09-25 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4326809e4d82"
down_revision: str | None = "f5dc1737eea9"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.create_table(
        "holidays",
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=True),
    )

    op.add_column(
        "service_catalog",
        sa.Column("parts_available", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # Distinguishes appointments actually created by the Phase 5 scheduling engine from
    # Phase 1's synthetic historical data, which used a simplified capacity heuristic (not
    # real conflict-free scheduling) and already contains ~20k technician-time overlaps a
    # blanket exclusion constraint could never validate against. Defaults false so every
    # pre-existing row is automatically outside the constraint below; the booking engine sets
    # it true explicitly.
    op.add_column(
        "appointments",
        sa.Column("booked_via_engine", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Section 5.2: "Booking in a single DB transaction with SELECT ... FOR UPDATE on the bay
    # and technician rows or an exclusion constraint on tstzrange to prevent double booking."
    # GiST exclusion constraints give a DB-enforced guarantee with no race window at all (the
    # concurrency DoD test -- 50 parallel bookings for the same slot, exactly one succeeds --
    # is what this exists to satisfy). Partial: cancelled/no-show appointments never conflict,
    # and only booked_via_engine rows are covered (see column comment above).
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE appointments
        ADD CONSTRAINT ex_appointments_technician_no_overlap
        EXCLUDE USING gist (
            technician_id WITH =,
            tstzrange(scheduled_start, scheduled_end, '[)') WITH &&
        )
        WHERE (status IN ('booked', 'completed') AND technician_id IS NOT NULL AND booked_via_engine)
        """
    )
    op.execute(
        """
        ALTER TABLE appointments
        ADD CONSTRAINT ex_appointments_bay_no_overlap
        EXCLUDE USING gist (
            location_id WITH =,
            bay_number WITH =,
            tstzrange(scheduled_start, scheduled_end, '[)') WITH &&
        )
        WHERE (status IN ('booked', 'completed') AND bay_number IS NOT NULL AND booked_via_engine)
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS ex_appointments_bay_no_overlap")
    op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS ex_appointments_technician_no_overlap")
    op.drop_column("appointments", "booked_via_engine")
    op.drop_column("service_catalog", "parts_available")
    op.drop_table("holidays")
