"""AgentDecisionEmbedding model: vector index for past-decision RAG.

Populated when an AgentDecision is persisted (Phase 3). The Reflect agent
queries this table to find the K most-similar past decisions for the same
ticker (and a few cross-ticker), feeding their realized outcomes into the
current run's prompt context.

Embedding format mirrors `DocEmbedding` (JSON-serialized list-of-floats);
upgrades to `pgvector` deferred until our embedding volume justifies it.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class AgentDecisionEmbedding(Base):
    """Embedding of an AgentDecision's thesis_text for memory RAG."""

    __tablename__ = "agent_decision_embedding"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    agent_decision_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID,
        ForeignKey("agent_decisions.id", ondelete="CASCADE"),
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
        return f"<AgentDecisionEmbedding(decision={self.agent_decision_id}, model={self.model})>"

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
            "agent_decision_id": str(self.agent_decision_id),
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
