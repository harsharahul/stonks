"""
User model for Authentik OIDC-authenticated users
"""
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import String, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class User(Base):
    """
    Authenticated user — identity sourced from Authentik OIDC.
    Auto-created on first successful login.
    """
    __tablename__ = "users"

    id: Mapped[PG_UUID] = mapped_column(PG_UUID, primary_key=True, server_default=func.gen_random_uuid())

    # Identity (from OIDC claims)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Auth provider linkage
    auth_provider: Mapped[str] = mapped_column(String, nullable=False, default="authentik")
    provider_user_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)  # OIDC 'sub' claim

    # Authorization
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")  # "user" | "admin"

    # Preferences (JSON blob — theme, alert settings, default views, etc.)
    preferences: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User(email={self.email}, role={self.role})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "email": self.email,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "role": self.role,
            "preferences": self.preferences or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
