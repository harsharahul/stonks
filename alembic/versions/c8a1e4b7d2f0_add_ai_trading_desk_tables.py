"""add_ai_trading_desk_tables

Schema for the AI Trading Desk: per-run logs, per-agent briefs, final
decisions + retrospective outcomes, embeddings for memory + Ask-the-Desk
RAG, and the universe membership history.

Revision ID: c8a1e4b7d2f0
Revises: b2dd3b44a02e
Create Date: 2026-04-28 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c8a1e4b7d2f0"
down_revision: Union[str, None] = "b2dd3b44a02e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # agent_runs ----------------------------------------------------------
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("run_started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("run_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("model_version", sa.String(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("tokens_in_total", sa.Integer(), nullable=True),
        sa.Column("tokens_out_total", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_ticker", "agent_runs", ["ticker"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])

    # agent_briefs --------------------------------------------------------
    op.create_table(
        "agent_briefs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=False),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("conviction", sa.Numeric(5, 3), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_briefs_agent_run_id", "agent_briefs", ["agent_run_id"])
    op.create_index("ix_agent_briefs_agent_name", "agent_briefs", ["agent_name"])

    # agent_decisions -----------------------------------------------------
    op.create_table(
        "agent_decisions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("conviction", sa.Numeric(5, 3), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=True),
        sa.Column("entry_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("stop_loss", sa.Numeric(18, 4), nullable=True),
        sa.Column("take_profit", sa.Numeric(18, 4), nullable=True),
        sa.Column("position_pct", sa.Numeric(6, 3), nullable=True),
        sa.Column("thesis_text", sa.Text(), nullable=True),
        sa.Column("top_risks_json", sa.JSON(), nullable=True),
        sa.Column("features_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("pending", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_run_id", name="uq_agent_decisions_run"),
    )
    op.create_index("ix_agent_decisions_ticker", "agent_decisions", ["ticker"])
    op.create_index("ix_agent_decisions_pending", "agent_decisions", ["pending"])
    op.create_index(
        "ix_agent_decisions_ticker_as_of_date",
        "agent_decisions",
        ["ticker", "as_of_date"],
    )

    # agent_decision_outcomes ---------------------------------------------
    op.create_table(
        "agent_decision_outcomes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_decision_id", sa.UUID(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("realized_return_5d", sa.Numeric(10, 6), nullable=True),
        sa.Column("realized_return_30d", sa.Numeric(10, 6), nullable=True),
        sa.Column("spy_return_5d", sa.Numeric(10, 6), nullable=True),
        sa.Column("spy_return_30d", sa.Numeric(10, 6), nullable=True),
        sa.Column("alpha_5d", sa.Numeric(10, 6), nullable=True),
        sa.Column("alpha_30d", sa.Numeric(10, 6), nullable=True),
        sa.Column("hit_stop", sa.Boolean(), nullable=True),
        sa.Column("hit_target", sa.Boolean(), nullable=True),
        sa.Column("reflection_text", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agent_decision_id"], ["agent_decisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_decision_id", name="uq_agent_decision_outcomes_decision"),
    )

    # agent_decision_embedding -------------------------------------------
    op.create_table(
        "agent_decision_embedding",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_decision_id", sa.UUID(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("text_for_embedding", sa.Text(), nullable=True),
        sa.Column("model", sa.String(), nullable=False, server_default=sa.text("'nomic-embed-text'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_decision_id"], ["agent_decisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_decision_id", name="uq_agent_decision_embedding_decision"),
    )

    # agent_brief_embedding ----------------------------------------------
    op.create_table(
        "agent_brief_embedding",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_brief_id", sa.UUID(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("text_for_embedding", sa.Text(), nullable=True),
        sa.Column("model", sa.String(), nullable=False, server_default=sa.text("'nomic-embed-text'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_brief_id"], ["agent_briefs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_brief_id", name="uq_agent_brief_embedding_brief"),
    )

    # agent_universe_membership ------------------------------------------
    op.create_table(
        "agent_universe_membership",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("included_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("included_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Numeric(10, 4), nullable=True),
        sa.Column("reason", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_universe_membership_ticker", "agent_universe_membership", ["ticker"])
    op.create_index(
        "ix_agent_universe_membership_included_until",
        "agent_universe_membership",
        ["included_until"],
    )
    op.create_index(
        "ix_agent_universe_active",
        "agent_universe_membership",
        ["ticker", "included_until"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_universe_active", table_name="agent_universe_membership")
    op.drop_index("ix_agent_universe_membership_included_until", table_name="agent_universe_membership")
    op.drop_index("ix_agent_universe_membership_ticker", table_name="agent_universe_membership")
    op.drop_table("agent_universe_membership")

    op.drop_table("agent_brief_embedding")
    op.drop_table("agent_decision_embedding")
    op.drop_table("agent_decision_outcomes")

    op.drop_index("ix_agent_decisions_ticker_as_of_date", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_pending", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_ticker", table_name="agent_decisions")
    op.drop_table("agent_decisions")

    op.drop_index("ix_agent_briefs_agent_name", table_name="agent_briefs")
    op.drop_index("ix_agent_briefs_agent_run_id", table_name="agent_briefs")
    op.drop_table("agent_briefs")

    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_ticker", table_name="agent_runs")
    op.drop_table("agent_runs")
