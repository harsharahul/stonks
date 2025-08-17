"""
Alert models for real-time notifications and user subscriptions
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Text, JSON, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Alert(Base):
    """
    Real-time alerts triggered by market events and signals
    """
    __tablename__ = "alerts"

    # Primary key
    id: Mapped[PG_UUID] = mapped_column(PG_UUID, primary_key=True, server_default=func.gen_random_uuid())
    
    # Alert targeting
    user_id: Mapped[Optional[PG_UUID]] = mapped_column(PG_UUID, nullable=True)  # NULL for system-wide alerts
    ticker: Mapped[str] = mapped_column(String, nullable=False, index=True)
    
    # Alert classification
    alert_type: Mapped[str] = mapped_column(String, nullable=False)  # 'price_spike', 'volume_surge', 'sentiment_change', etc.
    severity: Mapped[str] = mapped_column(String, nullable=False)  # 'low', 'medium', 'high', 'critical'
    
    # Alert content
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Timing and acknowledgment
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships and metadata
    signal_id: Mapped[Optional[PG_UUID]] = mapped_column(PG_UUID, ForeignKey("signals.id"), nullable=True)
    alert_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Indexing for performance
    # Note: Partitioning removed for simplicity, can be added later for scale
    
    def __repr__(self):
        return f"<Alert(ticker={self.ticker}, type={self.alert_type}, severity={self.severity})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "ticker": self.ticker,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "signal_id": str(self.signal_id) if self.signal_id else None,
            "metadata": self.alert_metadata or {},
            "age_minutes": self.age_minutes,
            "is_acknowledged": self.is_acknowledged
        }
    
    @property
    def is_acknowledged(self) -> bool:
        """Check if alert has been acknowledged"""
        return self.acknowledged_at is not None
    
    @property
    def age_minutes(self) -> float:
        """Get alert age in minutes"""
        if not self.triggered_at:
            return 0
        delta = datetime.utcnow() - self.triggered_at.replace(tzinfo=None)
        return delta.total_seconds() / 60
    
    def acknowledge(self):
        """Mark alert as acknowledged"""
        self.acknowledged_at = datetime.utcnow()
    
    def get_severity_color(self) -> str:
        """Get color code for severity level"""
        colors = {
            "low": "#10b981",      # green
            "medium": "#f59e0b",   # yellow  
            "high": "#ef4444",     # red
            "critical": "#dc2626"  # dark red
        }
        return colors.get(self.severity, "#6b7280")  # gray default


class AlertSubscription(Base):
    """
    User alert subscription preferences and configuration
    """
    __tablename__ = "alert_subscriptions"

    # Primary key
    id: Mapped[PG_UUID] = mapped_column(PG_UUID, primary_key=True, server_default=func.gen_random_uuid())
    
    # User targeting
    user_id: Mapped[PG_UUID] = mapped_column(PG_UUID, nullable=False, index=True)  # Future: user management
    ticker: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # NULL for all tickers
    
    # Subscription configuration
    alert_types: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)  # Which alert types to receive
    delivery_methods: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)  # ['websocket', 'email', 'webhook']
    thresholds: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Custom thresholds per alert type
    
    # Status and metadata
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<AlertSubscription(user_id={self.user_id}, ticker={self.ticker}, active={self.active})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "ticker": self.ticker,
            "alert_types": self.alert_types or [],
            "delivery_methods": self.delivery_methods or [],
            "thresholds": self.thresholds or {},
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def should_deliver_alert(self, alert: Alert) -> bool:
        """Check if this subscription should receive the given alert"""
        if not self.active:
            return False
        
        # Check ticker filter
        if self.ticker and self.ticker != alert.ticker:
            return False
        
        # Check alert type filter
        if alert.alert_type not in self.alert_types:
            return False
        
        # Check custom thresholds
        if self.thresholds and alert.alert_type in self.thresholds:
            threshold_config = self.thresholds[alert.alert_type]
            
            # Check severity threshold
            if "min_severity" in threshold_config:
                severity_levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
                min_level = severity_levels.get(threshold_config["min_severity"], 1)
                alert_level = severity_levels.get(alert.severity, 1)
                if alert_level < min_level:
                    return False
        
        return True
    
    def update_thresholds(self, alert_type: str, thresholds: Dict[str, Any]):
        """Update thresholds for specific alert type"""
        if not self.thresholds:
            self.thresholds = {}
        self.thresholds[alert_type] = thresholds
        self.updated_at = datetime.utcnow()
