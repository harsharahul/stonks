from datetime import datetime
from typing import Any

from sqlalchemy.orm import DeclarativeBase, declared_attr, Mapped, mapped_column
from sqlalchemy import func, DateTime


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UUIDPrimaryKeyMixin:
    from sqlalchemy.dialects.postgresql import UUID

    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
