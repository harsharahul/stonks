"""
Signal model for storing trading signals and market insights
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import String, DateTime, Numeric, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class Signal(Base):
    """
    Trading signals generated from analytics features
    Represents actionable insights with strength and confidence scoring
    """
    __tablename__ = "signals"

    # Primary key
    id: Mapped[PG_UUID] = mapped_column(PG_UUID, primary_key=True, server_default=func.gen_random_uuid())
    
    # Signal identification
    ticker: Mapped[str] = mapped_column(String, nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String, nullable=False)  # 'momentum', 'sentiment_spike', 'wsb_viral', etc.
    
    # Signal characteristics
    strength: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)  # -1.0 to 1.0
    confidence: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)  # 0.0 to 1.0
    direction: Mapped[str] = mapped_column(String, nullable=False)  # 'bullish', 'bearish', 'neutral'
    timeframe: Mapped[str] = mapped_column(String, nullable=False)  # 'intraday', 'daily', 'weekly'
    
    # Timing
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Metadata and provenance
    signal_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    features_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str] = mapped_column(String, nullable=False, default="v1.0.0")
    
    # Indexing for performance
    # Note: Partitioning removed for simplicity, can be added later for scale
    
    def __repr__(self):
        return f"<Signal(ticker={self.ticker}, type={self.signal_type}, strength={self.strength}, direction={self.direction})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "ticker": self.ticker,
            "signal_type": self.signal_type,
            "strength": float(self.strength),
            "confidence": float(self.confidence),
            "direction": self.direction,
            "timeframe": self.timeframe,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.signal_metadata or {},
            "features_snapshot": self.features_snapshot or {},
            "model_version": self.model_version
        }
    
    @property
    def is_expired(self) -> bool:
        """Check if signal has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)
    
    @property
    def age_hours(self) -> float:
        """Get signal age in hours"""
        if not self.generated_at:
            return 0
        delta = datetime.utcnow() - self.generated_at.replace(tzinfo=None)
        return delta.total_seconds() / 3600
    
    def get_display_strength(self) -> str:
        """Get human-readable strength description"""
        abs_strength = abs(self.strength)
        if abs_strength >= 0.8:
            return "Very Strong"
        elif abs_strength >= 0.6:
            return "Strong"
        elif abs_strength >= 0.4:
            return "Moderate"
        elif abs_strength >= 0.2:
            return "Weak"
        else:
            return "Very Weak"
    
    def get_display_confidence(self) -> str:
        """Get human-readable confidence description"""
        if self.confidence >= 0.8:
            return "High"
        elif self.confidence >= 0.6:
            return "Medium"
        elif self.confidence >= 0.4:
            return "Low"
        else:
            return "Very Low"