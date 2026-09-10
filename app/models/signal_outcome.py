"""SignalOutcome: realized forward return for one emitted Signal.

One row per scored signal. The nightly scorer fills entry/exit closes from the
prices table once the horizon window has elapsed, then ``win`` records whether
the signal's direction called the move correctly. Per-source aggregates
(win rate, avg return) are computed from these rows at query time, this is
the raw material for source track records, not a rollup table.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class SignalOutcome(Base):
    __tablename__ = "signal_outcomes"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    # SET NULL, not CASCADE: an outcome is a durable track record and must
    # outlive the signal it scored, which signal cleanup deletes after the
    # scoring window. The columns below are denormalized for exactly this.
    signal_id: Mapped[Optional[PG_UUID]] = mapped_column(
        PG_UUID, ForeignKey("signals.id", ondelete="SET NULL"), nullable=True, unique=True, index=True
    )

    # Denormalized from the signal so aggregates survive signal cleanup
    ticker: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String, nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    entry_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    exit_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    realized_return: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    win: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": str(self.signal_id),
            "ticker": self.ticker,
            "source": self.source,
            "signal_type": self.signal_type,
            "direction": self.direction,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "horizon_days": self.horizon_days,
            "entry_price": float(self.entry_price) if self.entry_price is not None else None,
            "exit_price": float(self.exit_price) if self.exit_price is not None else None,
            "realized_return": float(self.realized_return) if self.realized_return is not None else None,
            "win": self.win,
        }
