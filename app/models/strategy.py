"""Strategy: a followable trading strategy owned by a user.

The social spine of the platform. Every strategy's trades come from the
BrokerOrder ledger (rows tagged with strategy_id), so track records are
computed from real broker fills — never self-reported. ``kind`` says where
the strategy's trade intents come from:

- manual:      the owner tags their own trades
- desk:        the AI Trading Desk (platform-owned, first public strategy)
- signal_rule: subscribed to signal types/thresholds (Phase 3)
- bot_api:     external bot pushing intents via scoped token (Phase 4)
- bot_llm:     no-code LLM bot using the owner's LLM API key (Phase 4)

``disclosure`` is REQUIRED for public strategies: the owner's conflict
statement (e.g. "I hold positions in what I trade here"). Compliance: the
platform never recommends strategies; discovery ranks by objective verified
metrics only, and every public surface carries a not-investment-advice
disclaimer.
"""
import re
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base

STRATEGY_KINDS = ("manual", "desk", "signal_rule", "bot_api", "bot_llm")
STRATEGY_VISIBILITIES = ("private", "unlisted", "public")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:60] or "strategy"


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    owner_user_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String, nullable=False, default="private")
    kind: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    # Owner's conflict-of-interest statement — required to go public.
    disclosure: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_strategy_owner_name"),
    )

    def to_dict(self, *, include_private: bool = False) -> Dict[str, Any]:
        d = {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "visibility": self.visibility,
            "kind": self.kind,
            "disclosure": self.disclosure,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_private:
            d["config"] = self.config or {}
        return d
