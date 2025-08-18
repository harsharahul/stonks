from typing import Optional, List
from sqlalchemy import Text, ForeignKey, DateTime, Numeric, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class Article(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "articles"

    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("data_sources.id"), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tickers: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    sentiment: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    entities: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    article_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Enhanced analytics fields
    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hash_sha256: Mapped[Optional[str]] = mapped_column(Text, nullable=True, unique=True)