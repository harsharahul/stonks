"""add_broker_tables

Per-user Alpaca brokerage: encrypted account links + local order ledger.

Revision ID: d4f2a91c5e88
Revises: c8a1e4b7d2f0
Create Date: 2026-06-09 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d4f2a91c5e88"
down_revision: Union[str, None] = "c8a1e4b7d2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_broker_accounts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default=sa.text("'alpaca'")),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("secret_key_encrypted", sa.Text(), nullable=False),
        sa.Column("paper", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_execute", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("account_label", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_broker_provider"),
    )
    op.create_index("ix_user_broker_accounts_user_id", "user_broker_accounts", ["user_id"])

    op.create_table(
        "broker_orders",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("broker_account_id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("qty", sa.Numeric(18, 6), nullable=True),
        sa.Column("notional", sa.Numeric(18, 2), nullable=True),
        sa.Column("order_type", sa.String(), nullable=False, server_default=sa.text("'market'")),
        sa.Column("time_in_force", sa.String(), nullable=False, server_default=sa.text("'day'")),
        sa.Column("limit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("stop_loss_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("take_profit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("paper", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("client_order_id", sa.String(), nullable=False),
        sa.Column("alpaca_order_id", sa.String(), nullable=True),
        sa.Column("filled_qty", sa.Numeric(18, 6), nullable=True),
        sa.Column("filled_avg_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("source_ref", sa.String(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["broker_account_id"], ["user_broker_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_order_id", name="uq_broker_orders_client_order_id"),
    )
    op.create_index("ix_broker_orders_user_id", "broker_orders", ["user_id"])
    op.create_index("ix_broker_orders_symbol", "broker_orders", ["symbol"])
    op.create_index("ix_broker_orders_status", "broker_orders", ["status"])
    op.create_index("ix_broker_orders_alpaca_order_id", "broker_orders", ["alpaca_order_id"])
    op.create_index("ix_broker_orders_user_created", "broker_orders", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_broker_orders_user_created", table_name="broker_orders")
    op.drop_index("ix_broker_orders_alpaca_order_id", table_name="broker_orders")
    op.drop_index("ix_broker_orders_status", table_name="broker_orders")
    op.drop_index("ix_broker_orders_symbol", table_name="broker_orders")
    op.drop_index("ix_broker_orders_user_id", table_name="broker_orders")
    op.drop_table("broker_orders")

    op.drop_index("ix_user_broker_accounts_user_id", table_name="user_broker_accounts")
    op.drop_table("user_broker_accounts")
