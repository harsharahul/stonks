from typing import Optional, List
from datetime import date as date_type, datetime
from sqlalchemy import String, Date, Numeric, Integer, ARRAY, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TickerFeaturesDaily(Base):
    """
    Daily aggregated features per ticker with versioning
    Core feature store for deterministic analytics
    """
    __tablename__ = "ticker_features_daily"

    # Composite primary key
    ticker: Mapped[str] = mapped_column(String, primary_key=True)
    date: Mapped[date_type] = mapped_column(Date, primary_key=True)
    feature_version: Mapped[str] = mapped_column(String, primary_key=True, default="v1.0.0")
    
    # Sentiment features
    sent_mean_3d: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    sent_mean_7d: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    sent_mean_10d: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    sent_shock: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)  # z-score
    sent_volume_weighted: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    
    # Market features
    ret_1d: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    ret_5d: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    ret_20d: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    vol_z: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)  # volume z-score
    momentum_14d: Mapped[Optional[float]] = mapped_column(Numeric(8, 6), nullable=True)
    
    # Context features
    earnings_d: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # days to earnings
    conflict_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    novelty_mean_3d: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    
    # Retail sentiment features (WSB)
    wsb_sentiment_3d: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    wsb_sentiment_7d: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    wsb_mention_count_7d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wsb_engagement_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    retail_buzz_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    meme_stock_indicator: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    
    # Document references
    top_doc_ids: Mapped[Optional[List[str]]] = mapped_column(ARRAY(PG_UUID), nullable=True)
    article_count_7d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Versioning
    model_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    
    def __repr__(self):
        return f"<TickerFeaturesDaily(ticker={self.ticker}, date={self.date}, version={self.feature_version})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "ticker": self.ticker,
            "date": self.date.isoformat(),
            "feature_version": self.feature_version,
            "sentiment": {
                "mean_3d": float(self.sent_mean_3d) if self.sent_mean_3d else None,
                "mean_7d": float(self.sent_mean_7d) if self.sent_mean_7d else None,
                "mean_10d": float(self.sent_mean_10d) if self.sent_mean_10d else None,
                "shock": float(self.sent_shock) if self.sent_shock else None,
                "volume_weighted": float(self.sent_volume_weighted) if self.sent_volume_weighted else None,
            },
            "returns": {
                "ret_1d": float(self.ret_1d) if self.ret_1d else None,
                "ret_5d": float(self.ret_5d) if self.ret_5d else None,
                "ret_20d": float(self.ret_20d) if self.ret_20d else None,
                "momentum_14d": float(self.momentum_14d) if self.momentum_14d else None,
            },
            "context": {
                "vol_z": float(self.vol_z) if self.vol_z else None,
                "earnings_d": self.earnings_d,
                "conflict_score": float(self.conflict_score) if self.conflict_score else None,
                "novelty_mean_3d": float(self.novelty_mean_3d) if self.novelty_mean_3d else None,
                "article_count_7d": self.article_count_7d,
            },
            "retail_sentiment": {
                "wsb_sentiment_3d": float(self.wsb_sentiment_3d) if self.wsb_sentiment_3d else None,
                "wsb_sentiment_7d": float(self.wsb_sentiment_7d) if self.wsb_sentiment_7d else None,
                "wsb_mention_count_7d": self.wsb_mention_count_7d,
                "wsb_engagement_score": float(self.wsb_engagement_score) if self.wsb_engagement_score else None,
                "retail_buzz_score": float(self.retail_buzz_score) if self.retail_buzz_score else None,
                "meme_stock_indicator": float(self.meme_stock_indicator) if self.meme_stock_indicator else None,
            },
            "references": {
                "top_doc_ids": self.top_doc_ids or [],
            },
            "metadata": {
                "model_version": self.model_version,
                "created_at": self.created_at.isoformat() if self.created_at else None,
            }
        }
