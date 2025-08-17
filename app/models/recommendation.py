from typing import Optional
from sqlalchemy import ForeignKey, Text, Numeric, Date, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class Recommendation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "recommendations"

    stock_id: Mapped[str] = mapped_column(ForeignKey("stocks.id"), nullable=False, index=True)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Feature store integration
    feature_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    feature_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)