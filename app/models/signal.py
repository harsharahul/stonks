from typing import Optional
from sqlalchemy import ForeignKey, Text, Numeric, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class Signal(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "signals"

    stock_id: Mapped[str] = mapped_column(ForeignKey("stocks.id"), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    value: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    computed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
