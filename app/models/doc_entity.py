from typing import Optional
from datetime import datetime
from sqlalchemy import String, ForeignKey, Text, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DocEntity(Base):
    """
    Enhanced entity linking table with confidence scoring
    Links documents to tickers with multiple extraction methods
    """
    __tablename__ = "doc_entity"

    # Composite primary key
    doc_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), primary_key=True)
    ticker: Mapped[str] = mapped_column(String, primary_key=True)
    method: Mapped[str] = mapped_column(String, primary_key=True)  # extraction method
    
    # Entity information
    company_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)  # 0.0 to 1.0
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    
    def __repr__(self):
        return f"<DocEntity(doc_id={self.doc_id[:8]}..., ticker={self.ticker}, method={self.method}, confidence={self.confidence})>"
