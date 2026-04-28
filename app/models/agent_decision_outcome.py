"""AgentDecisionOutcome model: realized return + alpha vs SPY for an AgentDecision.

Populated retrospectively by the ``score_past_decisions`` Celery task when
the 5-day and 30-day windows after the decision close. One row per
AgentDecision. Powers the desk's track record header, the Reflect agent's
RAG context, and the bias-monitoring task.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class AgentDecisionOutcome(Base):
    """Realized return + alpha vs SPY scored after the decision window closes."""

    __tablename__ = "agent_decision_outcomes"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    agent_decision_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID,
        ForeignKey("agent_decisions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    realized_return_5d: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    realized_return_30d: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    spy_return_5d: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    spy_return_30d: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    alpha_5d: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    alpha_30d: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)

    hit_stop: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    hit_target: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    reflection_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AgentDecisionOutcome(decision_id={self.agent_decision_id}, "
            f"alpha_30d={self.alpha_30d})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        def _f(v: Optional[float]) -> Optional[float]:
            return float(v) if v is not None else None

        return {
            "id": str(self.id),
            "agent_decision_id": str(self.agent_decision_id),
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
            "realized_return_5d": _f(self.realized_return_5d),
            "realized_return_30d": _f(self.realized_return_30d),
            "spy_return_5d": _f(self.spy_return_5d),
            "spy_return_30d": _f(self.spy_return_30d),
            "alpha_5d": _f(self.alpha_5d),
            "alpha_30d": _f(self.alpha_30d),
            "hit_stop": self.hit_stop,
            "hit_target": self.hit_target,
            "reflection_text": self.reflection_text,
        }
