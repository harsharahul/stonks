"""AgentBrief model: per-agent output for an AgentRun.

Each desk run produces one AgentBrief row per (agent_name, round_index) pair:
- analysts (market, social, news, fundamentals): round_index=0
- bull/bear researchers: round_index=1, 2, ...
- research_manager, trader: round_index=0
- risk team (aggressive, conservative, neutral): round_index=1, 2, ...
- portfolio_manager: round_index=0
- reflect (Phase 3): round_index=0

``output_json`` is the structured agent output (Pydantic dump), ``output_text``
is the raw markdown rendering used by upstream prompts and persisted for
later RAG (Phase 4 Ask-the-Desk).
"""
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class AgentBrief(Base):
    """Single agent's output for one AgentRun."""

    __tablename__ = "agent_briefs"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    agent_run_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # market / social / news / fundamentals / bull / bear / research_manager / trader /
    # aggressive / conservative / neutral / portfolio_manager / reflect
    agent_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    round_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    output_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    output_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Self-reported confidence in [0,1]; NULL when the agent didn't produce one
    conviction: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)

    tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<AgentBrief(run={self.agent_run_id}, agent={self.agent_name}, "
            f"round={self.round_index})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "agent_run_id": str(self.agent_run_id),
            "agent_name": self.agent_name,
            "round_index": self.round_index,
            "output_json": self.output_json,
            "output_text": self.output_text,
            "conviction": float(self.conviction) if self.conviction is not None else None,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
