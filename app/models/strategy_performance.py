"""StrategyPerformanceDaily: nightly verified track-record snapshot.

Computed exclusively from FILLED BrokerOrder rows (real Alpaca fills) by
``app/tasks/strategy_performance.py``: never self-reported. Paper and live
are tracked separately and always labeled; mixing them would be the
screenshot-cherry-picking we exist to kill.
"""
from datetime import date as date_type, datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class StrategyPerformanceDaily(Base):
    __tablename__ = "strategy_performance_daily"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    strategy_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    paper: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed_trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    realized_pnl: Mapped[Optional[float]] = mapped_column(Numeric(18, 2), nullable=True)
    avg_return_pct: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    max_drawdown_pct: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("strategy_id", "date", "paper", name="uq_strategy_perf_day"),
    )

    def to_dict(self) -> Dict[str, Any]:
        def _f(v):
            return float(v) if v is not None else None

        return {
            "date": self.date.isoformat() if self.date else None,
            "paper": self.paper,
            "trade_count": self.trade_count,
            "closed_trade_count": self.closed_trade_count,
            "win_count": self.win_count,
            "win_rate": (self.win_count / self.closed_trade_count) if self.closed_trade_count else None,
            "realized_pnl": _f(self.realized_pnl),
            "avg_return_pct": _f(self.avg_return_pct),
            "max_drawdown_pct": _f(self.max_drawdown_pct),
        }
