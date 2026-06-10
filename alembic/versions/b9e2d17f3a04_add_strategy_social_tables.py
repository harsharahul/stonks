"""add strategy social tables (strategies, follows, performance) + broker_orders.strategy_id

Revision ID: b9e2d17f3a04
Revises: f1a9c44e7b31
Create Date: 2026-06-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b9e2d17f3a04"
down_revision: Union[str, None] = "f1a9c44e7b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(), nullable=False, server_default="private"),
        sa.Column("kind", sa.String(), nullable=False, server_default="manual"),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("disclosure", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_strategy_owner_name"),
    )
    op.create_index("ix_strategies_owner_user_id", "strategies", ["owner_user_id"])
    op.create_index("ix_strategies_slug", "strategies", ["slug"])

    op.create_table(
        "strategy_follows",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("follower_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("copy_mode", sa.String(), nullable=False, server_default="notify"),
        sa.Column("risk_config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("strategy_id", "follower_user_id", name="uq_strategy_follower"),
    )
    op.create_index("ix_strategy_follows_strategy_id", "strategy_follows", ["strategy_id"])
    op.create_index("ix_strategy_follows_follower_user_id", "strategy_follows", ["follower_user_id"])

    op.create_table(
        "strategy_performance_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("paper", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("trade_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("closed_trade_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("win_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("realized_pnl", sa.Numeric(18, 2), nullable=True),
        sa.Column("avg_return_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("max_drawdown_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("strategy_id", "date", "paper", name="uq_strategy_perf_day"),
    )
    op.create_index("ix_strategy_performance_daily_strategy_id", "strategy_performance_daily", ["strategy_id"])

    op.add_column(
        "broker_orders",
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_broker_orders_strategy_id", "broker_orders", ["strategy_id"])


def downgrade() -> None:
    op.drop_index("ix_broker_orders_strategy_id", table_name="broker_orders")
    op.drop_column("broker_orders", "strategy_id")
    op.drop_index("ix_strategy_performance_daily_strategy_id", table_name="strategy_performance_daily")
    op.drop_table("strategy_performance_daily")
    op.drop_index("ix_strategy_follows_follower_user_id", table_name="strategy_follows")
    op.drop_index("ix_strategy_follows_strategy_id", table_name="strategy_follows")
    op.drop_table("strategy_follows")
    op.drop_index("ix_strategies_slug", table_name="strategies")
    op.drop_index("ix_strategies_owner_user_id", table_name="strategies")
    op.drop_table("strategies")
