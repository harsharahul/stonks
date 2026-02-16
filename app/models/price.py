from sqlalchemy import ForeignKey, DateTime, Numeric, BigInteger, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.models.base import Base, UUIDPrimaryKeyMixin


class Price(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "prices"

    # Legacy columns (used by older ingestion paths)
    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="yfinance")
    price_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # FK-based columns
    stock_id: Mapped[Optional[PG_UUID]] = mapped_column(PG_UUID, ForeignKey("stocks.id"), nullable=True, index=True)
    ts: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # OHLCV columns (match actual DB schema)
    open_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    high: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    low: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    close: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    adjusted_close: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
