"""conversation state and llm token budget

Revision ID: 6451189be429
Revises: db1b3eda0b5e
Create Date: 2026-09-24 13:43:57.852018

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6451189be429'
down_revision: str | None = 'db1b3eda0b5e'
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("state", sa.JSON(), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("tokens_used_total", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("conversations", "tokens_used_total")
    op.drop_column("conversations", "state")
