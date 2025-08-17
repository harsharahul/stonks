from typing import Optional
from datetime import datetime
from sqlalchemy import String, ForeignKey, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DocEmbedding(Base):
    """
    Document embeddings for vector search and LLM synthesis
    Optional table - only used when vector search capabilities are enabled
    """
    __tablename__ = "doc_embedding"

    # Primary key
    doc_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), primary_key=True)
    
    # Embedding data (stored as JSON text for now, can be converted to VECTOR type if pgvector available)
    embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String, default="text-embedding-ada-002", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    
    def __repr__(self):
        return f"<DocEmbedding(doc_id={self.doc_id[:8]}..., model={self.model})>"
    
    def set_embedding_vector(self, vector: list) -> None:
        """Store embedding vector as JSON string"""
        import json
        self.embedding = json.dumps(vector)
    
    def get_embedding_vector(self) -> Optional[list]:
        """Retrieve embedding vector from JSON string"""
        if not self.embedding:
            return None
        import json
        try:
            return json.loads(self.embedding)
        except json.JSONDecodeError:
            return None
