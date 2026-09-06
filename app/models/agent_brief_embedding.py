"""AgentBriefEmbedding model: vector index for Ask-the-Desk RAG.

Populated for each AgentBrief in Phase 4. The Ask-the-Desk endpoint
(`POST /desk/{ticker}/ask`) embeds the user's question, retrieves the K
most-similar briefs for that ticker, and feeds them as context to a small
synthesis call: no full re-run.

Separate from `agent_decision_embedding` because briefs and decisions are
different shapes and different retrieval patterns.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class AgentBriefEmbedding(Base):
    """Embedding of an AgentBrief's output_text for Ask-the-Desk RAG."""

    __tablename__ = "agent_brief_embedding"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    agent_brief_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID,
        ForeignKey("agent_briefs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text_for_embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String, nullable=False, default="nomic-embed-text")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AgentBriefEmbedding(brief={self.agent_brief_id}, model={self.model})>"

    def set_embedding_vector(self, vector: List[float]) -> None:
        import json
        self.embedding = json.dumps(vector)

    def get_embedding_vector(self) -> Optional[List[float]]:
        if not self.embedding:
            return None
        import json
        try:
            return json.loads(self.embedding)
        except json.JSONDecodeError:
            return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "agent_brief_id": str(self.agent_brief_id),
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
