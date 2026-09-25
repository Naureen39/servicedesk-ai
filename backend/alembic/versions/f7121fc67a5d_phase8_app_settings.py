"""phase8 app settings

Revision ID: f7121fc67a5d
Revises: 417be7c07f0a
Create Date: 2026-09-25 12:31:36.213714

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7121fc67a5d'
down_revision: str | None = '417be7c07f0a'
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("llm_primary", sa.String(20), nullable=False, server_default="groq"),
        sa.Column("confidence_threshold", sa.Numeric(4, 3), nullable=False, server_default="0.55"),
        sa.Column("cache_similarity_threshold", sa.Numeric(4, 3), nullable=False, server_default="0.92"),
        sa.Column("daily_budget_groq", sa.Integer, nullable=False, server_default="900"),
        sa.Column("daily_budget_gemini", sa.Integer, nullable=False, server_default="1400"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    # Singleton row -- the portal edits settings in place, never creates a second row.
    op.execute("INSERT INTO app_settings (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("app_settings")
