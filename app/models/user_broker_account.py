"""UserBrokerAccount: a user's linked brokerage account (Alpaca).

One row per (user, provider). API credentials are Fernet-encrypted at rest
with `settings.BROKER_CREDS_ENCRYPTION_KEY`; plaintext keys are never
persisted, logged, or returned by the API after the initial link call.

Safety posture (v1):
- `paper` defaults TRUE; linking a live account requires an explicit flag
  at the API layer and live order placement re-confirms per order.
- `auto_execute` defaults FALSE and is reserved for a future release:
  v1 only places orders a user explicitly confirms in the UI.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class UserBrokerAccount(Base):
    """Linked brokerage account with encrypted credentials."""

    __tablename__ = "user_broker_accounts"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String, nullable=False, default="alpaca")

    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    secret_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    paper: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_execute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Display-only hint, e.g. "PA3X...9F2", never the full account number.
    account_label: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_broker_provider"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserBrokerAccount(user={self.user_id}, provider={self.provider}, "
            f"paper={self.paper}, active={self.is_active})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """API-safe representation: never includes credentials."""
        return {
            "id": str(self.id),
            "provider": self.provider,
            "paper": self.paper,
            "auto_execute": self.auto_execute,
            "is_active": self.is_active,
            "account_label": self.account_label,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else None,
        }
