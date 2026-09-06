"""
Watchlist model: per-user saved/favorited stocks
"""
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import String, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class WatchlistItem(Base):
    """
    A single stock on a user's watchlist.
    (user_id, stock_id) is unique: one entry per stock per user.
    """
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "stock_id", name="uq_watchlist_user_stock"),
    )

    id: Mapped[PG_UUID] = mapped_column(PG_UUID, primary_key=True, server_default=func.gen_random_uuid())

    user_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stock_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates=None)
    stock = relationship("Stock", back_populates=None)

    def __repr__(self):
        return f"<WatchlistItem(user_id={self.user_id}, stock_id={self.stock_id})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "stock_id": str(self.stock_id),
            "notes": self.notes,
            "added_at": self.added_at.isoformat() if self.added_at else None,
            # stock fields populated by endpoints when joining
            "symbol": self.stock.symbol if self.stock else None,
            "company_name": self.stock.company_name if self.stock else None,
        }
