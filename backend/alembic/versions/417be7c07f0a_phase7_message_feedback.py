"""phase7 message feedback

Revision ID: 417be7c07f0a
Revises: f3fbe9f371a4
Create Date: 2026-09-25 09:13:38.691635

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '417be7c07f0a'
down_revision: str | None = 'f3fbe9f371a4'
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("helpful", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "helpful")
