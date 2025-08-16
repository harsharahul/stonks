from typing import Optional
from sqlalchemy import String, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class DataSource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "data_sources"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reliability_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), default=0.800)
