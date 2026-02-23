from typing import Optional
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import func

from app.models.base import Base, UUIDPrimaryKeyMixin


class StockKnowledge(UUIDPrimaryKeyMixin, Base):
    """
    Evolving per-ticker analytical intelligence that survives article deletion.

    Updated nightly by update_stock_knowledge_task after article cleanup runs.
    The raw articles are eventually deleted, but the distilled insights live here.
    """
    __tablename__ = "stock_knowledge"

    ticker: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)

    # LLM-generated analyst note (None if no LLM configured)
    narrative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamped event log: {"events": [{date, title, sentiment, url}, ...]}
    # Capped at 50 most recent significant events
    key_events: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Weekly sentiment rolling window: {"weekly": [{week, avg_sentiment, count}, ...]}
    # Capped at 52 weeks (1 year rolling)
    sentiment_trend: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Running total of articles processed into this knowledge record
    article_count_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self):
        return f"<StockKnowledge(ticker={self.ticker}, articles={self.article_count_processed})>"
