"""AgentDecision model: final desk decision for an AgentRun.

One row per AgentRun (1:1 with `agent_run_id`). Captures the Portfolio
Manager's final BUY/HOLD/SELL with conviction, sizing, stops, thesis, and a
snapshot of the features that drove it. ``pending=true`` until the
``score_past_decisions`` Celery task fills the matching
``agent_decision_outcomes`` row when the 5d / 30d windows close.
"""
from datetime import date, datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class AgentDecision(Base):
    """Final BUY / HOLD / SELL decision produced by the desk pipeline."""

    __tablename__ = "agent_decisions"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    agent_run_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    ticker: Mapped[str] = mapped_column(String, nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    # BUY | OVERWEIGHT | HOLD | UNDERWEIGHT | SELL  (matches upstream PortfolioRating)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    conviction: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    horizon_days: Mapped[Optional[int]] = mapped_column(nullable=True)

    entry_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    stop_loss: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    position_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 3), nullable=True)

    thesis_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    top_risks_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    features_snapshot_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_agent_decisions_ticker_as_of_date", "ticker", "as_of_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentDecision(ticker={self.ticker}, as_of={self.as_of_date}, "
            f"decision={self.decision}, conviction={self.conviction})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "agent_run_id": str(self.agent_run_id),
            "ticker": self.ticker,
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date else None,
            "decision": self.decision,
            "conviction": float(self.conviction),
            "horizon_days": self.horizon_days,
            "entry_price": float(self.entry_price) if self.entry_price is not None else None,
            "stop_loss": float(self.stop_loss) if self.stop_loss is not None else None,
            "take_profit": float(self.take_profit) if self.take_profit is not None else None,
            "position_pct": float(self.position_pct) if self.position_pct is not None else None,
            "thesis_text": self.thesis_text,
            "top_risks_json": self.top_risks_json,
            "features_snapshot_json": self.features_snapshot_json,
            "pending": self.pending,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
