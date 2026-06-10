"""SignalSourceState: per-deployment admin state for a registered signal plugin.

The plugin *code* lives in the registry (app/signals/); this row holds what
operators control at runtime: the enabled toggle, optional config overrides,
and the last-run health snapshot the admin dashboard displays. Rows are
created lazily by the dispatcher the first time it sees a registered source.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class SignalSourceState(Base):
    __tablename__ = "signal_source_states"

    id: Mapped[PG_UUID] = mapped_column(
        PG_UUID, primary_key=True, server_default=func.gen_random_uuid()
    )
    source_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Plugin-specific config overrides (merged over plugin defaults at dispatch)
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # success | error | skipped_config | disabled
    last_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signals_emitted_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "enabled": self.enabled,
            "config": self.config or {},
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "signals_emitted_total": self.signals_emitted_total,
        }
