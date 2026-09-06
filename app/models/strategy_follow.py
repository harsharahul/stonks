"""StrategyFollow: a user following a strategy.

``copy_mode`` ladder (legal gates researched 2026-06, see plan):
- notify:     trade alerts + one-click prefilled ticket (self-directed): Phase 2
- paper_auto: opt-in auto-mirroring on PAPER accounts only, Phase 3
- live_auto:  RESERVED. Hard-blocked until RIA registration or BD/RIA
              partnership (In re Weiss Research; Autopilot Advisers precedent).
"""
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, String, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

COPY_MODES = ("notify", "paper_auto", "live_auto")


class StrategyFollow(Base):
    __tablename__ = "strategy_follows"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    strategy_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    follower_user_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    copy_mode: Mapped[str] = mapped_column(String, nullable=False, default="notify")
    # Phase 3+: per-follow sizing caps (max % of equity per trade, max open positions, ...)
    risk_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("strategy_id", "follower_user_id", name="uq_strategy_follower"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": str(self.strategy_id),
            "copy_mode": self.copy_mode,
            "risk_config": self.risk_config or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
