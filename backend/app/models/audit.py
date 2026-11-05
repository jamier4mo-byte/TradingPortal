from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UTCDateTime, utcnow


class AuditLog(Base):
    """Who did what to which record. Written by the services on every sensitive change."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow, index=True)
