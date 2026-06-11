"""add signal_outcomes table for per-source signal track records

Revision ID: c7d4e9f2a815
Revises: b9e2d17f3a04
Create Date: 2026-06-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7d4e9f2a815"
down_revision: Union[str, None] = "b9e2d17f3a04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signal_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signals.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("entry_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("exit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("realized_return", sa.Numeric(10, 6), nullable=True),
        sa.Column("win", sa.Boolean(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_signal_outcomes_signal_id", "signal_outcomes", ["signal_id"], unique=True)
    op.create_index("ix_signal_outcomes_source", "signal_outcomes", ["source"])
    op.create_index("ix_signal_outcomes_ticker", "signal_outcomes", ["ticker"])


def downgrade() -> None:
    op.drop_index("ix_signal_outcomes_ticker", table_name="signal_outcomes")
    op.drop_index("ix_signal_outcomes_source", table_name="signal_outcomes")
    op.drop_index("ix_signal_outcomes_signal_id", table_name="signal_outcomes")
    op.drop_table("signal_outcomes")
