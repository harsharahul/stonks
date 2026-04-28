"""AgentRun model: per-ticker desk workflow execution log.

One row per (ticker, run_started_at) pair. Created when a Celery task starts a
run; updated to ``succeeded``/``failed``/``stale`` when the workflow finishes
or fails. Briefs and the final decision are linked to this row via FK.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class AgentRun(Base):
    """Per-run execution log for the AI Trading Desk pipeline."""

    __tablename__ = "agent_runs"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    ticker: Mapped[str] = mapped_column(String, nullable=False, index=True)

    run_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    run_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # pending → running → succeeded | failed | stale
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", index=True)
    # nightly | event:<reason> | on_demand | manual
    trigger: Mapped[str] = mapped_column(String, nullable=False)

    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tokens_in_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_out_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AgentRun(id={self.id}, ticker={self.ticker}, "
            f"status={self.status}, trigger={self.trigger})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "ticker": self.ticker,
            "run_started_at": self.run_started_at.isoformat() if self.run_started_at else None,
            "run_completed_at": self.run_completed_at.isoformat() if self.run_completed_at else None,
            "status": self.status,
            "trigger": self.trigger,
            "latency_ms": self.latency_ms,
            "model": self.model,
            "model_version": self.model_version,
            "error": self.error,
            "tokens_in_total": self.tokens_in_total,
            "tokens_out_total": self.tokens_out_total,
        }
