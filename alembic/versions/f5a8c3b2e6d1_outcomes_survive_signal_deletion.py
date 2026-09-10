"""Signal outcomes survive signal deletion.

The verified track record must outlive the signal it scored. Signal cleanup
deletes signals after the scoring window, and the outcome foreign key used
ON DELETE CASCADE, which erased the track record along with the signal. Make
signal_id nullable and switch the constraint to ON DELETE SET NULL so the
denormalized outcome row remains.

Revision ID: f5a8c3b2e6d1
Revises: e4f7a2c9b1d3
"""
from alembic import op

revision = "f5a8c3b2e6d1"
down_revision = "e4f7a2c9b1d3"
branch_labels = None
depends_on = None

_FK = "signal_outcomes_signal_id_fkey"


def upgrade() -> None:
    op.alter_column("signal_outcomes", "signal_id", nullable=True)
    op.drop_constraint(_FK, "signal_outcomes", type_="foreignkey")
    op.create_foreign_key(
        _FK, "signal_outcomes", "signals", ["signal_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint(_FK, "signal_outcomes", type_="foreignkey")
    op.create_foreign_key(
        _FK, "signal_outcomes", "signals", ["signal_id"], ["id"], ondelete="CASCADE"
    )
    op.alter_column("signal_outcomes", "signal_id", nullable=False)
