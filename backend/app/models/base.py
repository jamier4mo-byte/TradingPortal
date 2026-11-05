"""Declarative base and the shared mixins every owned record uses."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """SQLite drops the timezone; store UTC and always hand back aware datetimes."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class OwnerMixin:
    """Every owned record: owner_id points at users.id. Members change only their own."""

    @declared_attr
    def owner_id(cls) -> Mapped[int]:  # noqa: N805
        return mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)


class OwnedRecordMixin(TimestampMixin, SoftDeleteMixin, OwnerMixin):
    pass
