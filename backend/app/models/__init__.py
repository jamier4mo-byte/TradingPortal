"""Import every model here so Alembic and the app see the whole schema."""

from .api_key import UserApiKey
from .audit import AuditLog
from .base import Base, OwnedRecordMixin, OwnerMixin, SoftDeleteMixin, TimestampMixin, utcnow
from .tag import TAG_CATEGORIES, Tag
from .user import OWNER_COLOURS, Invite, Passkey, PasswordReset, Session, User

__all__ = [
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
