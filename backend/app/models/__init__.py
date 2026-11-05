"""Import every model here so Alembic and the app see the whole schema."""

from .api_key import UserApiKey
from .audit import AuditLog
from .base import Base, OwnedRecordMixin, OwnerMixin, SoftDeleteMixin, TimestampMixin, utcnow
from .journal import (
    DEFAULT_REASONING_TEMPLATE,
    DEFAULT_RULES,
    MAX_EXTRA_SCREENSHOTS,
    SLOTS,
    Instrument,
    JournalSession,
    Screenshot,
    Strategy,
    Trade,
    trade_tags,
)
from .tag import TAG_CATEGORIES, Tag
from .user import OWNER_COLOURS, Invite, Passkey, PasswordReset, Session, User

__all__ = [
    "DEFAULT_REASONING_TEMPLATE",
    "DEFAULT_RULES",
    "MAX_EXTRA_SCREENSHOTS",
    "SLOTS",
    "Instrument",
    "JournalSession",
    "Screenshot",
    "Strategy",
    "Trade",
    "trade_tags",
    "OWNER_COLOURS",
    "TAG_CATEGORIES",
    "AuditLog",
    "Base",
    "Invite",
    "OwnedRecordMixin",
    "OwnerMixin",
    "Passkey",
    "PasswordReset",
    "Session",
    "SoftDeleteMixin",
    "Tag",
    "TimestampMixin",
    "User",
    "UserApiKey",
    "utcnow",
]
