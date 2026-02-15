from sqlalchemy import ForeignKey, DateTime, Numeric, BigInteger
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class Price(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "prices"

    stock_id: Mapped[PG_UUID] = mapped_column(PG_UUID, ForeignKey("stocks.id"), nullable=False, index=True)
    ts: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    open: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger)
    adjusted_close: Mapped[float] = mapped_column(Numeric(18, 6), nullable=True)
