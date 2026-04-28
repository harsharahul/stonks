"""AgentUniverseMembership model: which tickers the desk covers, and why.

Refreshed weekly (Sun 00:00 UTC) by `refresh_universe_membership` Celery task.
Each row says: from `included_at` to `included_until`, ticker X was in the
desk universe because (`reason`) with composite `score`. Ad-hoc inclusion
(via watchlist) and reserved "movers" slots use sentinel reasons.

We keep history (don't truncate on refresh) so we can answer "when did NVDA
enter/leave the universe?" later.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class AgentUniverseMembership(Base):
    """Membership history for the AI Trading Desk's coverage universe."""

    __tablename__ = "agent_universe_membership"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    ticker: Mapped[str] = mapped_column(String, nullable=False, index=True)

    included_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    included_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    score: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)

    # top_activity | watchlist | mover_reserve | manual
    reason: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("ix_agent_universe_active", "ticker", "included_until"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentUniverseMembership(ticker={self.ticker}, reason={self.reason}, "
            f"included_at={self.included_at})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "ticker": self.ticker,
            "included_at": self.included_at.isoformat() if self.included_at else None,
            "included_until": self.included_until.isoformat() if self.included_until else None,
            "score": float(self.score) if self.score is not None else None,
            "reason": self.reason,
        }
