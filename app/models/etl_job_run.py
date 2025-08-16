from typing import Optional
from sqlalchemy import Text, DateTime, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class ETLJobRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "etl_job_runs"

    job_name: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    items_processed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
