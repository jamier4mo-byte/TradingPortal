from datetime import datetime

from sqlalchemy import Boolean, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, OwnedRecordMixin, UTCDateTime


class UserApiKey(OwnedRecordMixin, Base):
    """A member's own provider key (e.g. Twelve Data), Fernet-encrypted. Plaintext never leaves the server."""

    __tablename__ = "user_api_keys"
    __table_args__ = (UniqueConstraint("owner_id", "provider", name="uq_user_api_keys_owner_provider"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
