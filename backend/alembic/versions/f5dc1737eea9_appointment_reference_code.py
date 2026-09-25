"""appointment reference code

Revision ID: f5dc1737eea9
Revises: 6451189be429
Create Date: 2026-09-24 13:50:52.845037

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5dc1737eea9'
down_revision: str | None = '6451189be429'
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("reference_code", sa.String(length=12), nullable=True))
    op.create_index("ix_appointments_reference_code", "appointments", ["reference_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_appointments_reference_code", table_name="appointments")
    op.drop_column("appointments", "reference_code")
