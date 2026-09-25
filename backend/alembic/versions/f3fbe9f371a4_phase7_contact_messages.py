"""phase7 contact messages

Revision ID: f3fbe9f371a4
Revises: 4326809e4d82
Create Date: 2026-09-25 09:03:00.395166

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3fbe9f371a4'
down_revision: str | None = '4326809e4d82'
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.create_table(
        "contact_messages",
        sa.Column("message_id", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(32)),
        sa.Column("location_id", sa.Integer, sa.ForeignKey("locations.location_id")),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_contact_messages_created_at", "contact_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_contact_messages_created_at", table_name="contact_messages")
    op.drop_table("contact_messages")
