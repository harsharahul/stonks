"""BrokerOrder: local ledger of every order Stonks submits to a brokerage.

The local row is created BEFORE the order is submitted (status='pending'),
then updated with the broker's response. `client_order_id` is deterministic
and unique so a retried submit can never double-place at the broker
(Alpaca rejects duplicate client_order_ids).

`source`/`source_ref` record provenance: 'manual' (user clicked trade),
'desk' (AI Trading Desk decision id), 'signal' (signal id) — the audit
trail for "why did Stonks place this order".
"""
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class BrokerOrder(Base):
    """One submitted (or attempted) brokerage order."""

    __tablename__ = "broker_orders"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    broker_account_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, ForeignKey("user_broker_accounts.id", ondelete="CASCADE"), nullable=False
    )

    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    side: Mapped[str] = mapped_column(String, nullable=False)  # buy | sell
    qty: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    notional: Mapped[Optional[float]] = mapped_column(Numeric(18, 2), nullable=True)
    order_type: Mapped[str] = mapped_column(String, nullable=False, default="market")  # market | limit
    time_in_force: Mapped[str] = mapped_column(String, nullable=False, default="day")
    limit_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    stop_loss_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    take_profit_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)

    # pending → submitted → filled | partially_filled | canceled | rejected | failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", index=True)
    paper: Mapped[bool] = mapped_column(nullable=False, default=True)

    client_order_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    alpaca_order_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    filled_qty: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    filled_avg_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)

    source: Mapped[str] = mapped_column(String, nullable=False, default="manual")  # manual | desk | signal
    source_ref: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Social layer: orders tagged to a strategy form its public trade feed
    # and verified track record (see app/models/strategy.py).
    strategy_id: Mapped[Optional[PG_UUID]] = mapped_column(
        PG_UUID, ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True, index=True
    )

    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_response: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_broker_orders_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<BrokerOrder(user={self.user_id}, {self.side} {self.symbol}, "
            f"status={self.status}, paper={self.paper})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        def _f(v):
            return float(v) if v is not None else None

        return {
            "id": str(self.id),
            "symbol": self.symbol,
            "side": self.side,
            "qty": _f(self.qty),
            "notional": _f(self.notional),
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "limit_price": _f(self.limit_price),
            "stop_loss_price": _f(self.stop_loss_price),
            "take_profit_price": _f(self.take_profit_price),
            "status": self.status,
            "paper": self.paper,
            "client_order_id": self.client_order_id,
            "alpaca_order_id": self.alpaca_order_id,
            "filled_qty": _f(self.filled_qty),
            "filled_avg_price": _f(self.filled_avg_price),
            "source": self.source,
            "source_ref": self.source_ref,
            "strategy_id": str(self.strategy_id) if self.strategy_id else None,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
        }
