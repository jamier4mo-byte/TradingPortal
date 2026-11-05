"""Per-user API-key vault (F1, F13). The plaintext never leaves the server and is never logged."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.security import decrypt_secret, encrypt_secret, utcnow
from ..models import User, UserApiKey
from . import audit

PROVIDERS = ("twelve_data",)


class KeyError_(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def _live(db: Session, user: User, provider: str) -> UserApiKey | None:
    return db.scalar(
        select(UserApiKey).where(
            UserApiKey.owner_id == user.id, UserApiKey.provider == provider, UserApiKey.deleted_at.is_(None)
        )
    )


def list_keys(db: Session, user: User) -> list[UserApiKey]:
    return list(
        db.scalars(select(UserApiKey).where(UserApiKey.owner_id == user.id, UserApiKey.deleted_at.is_(None)))
    )


def set_key(db: Session, user: User, provider: str, plaintext: str) -> UserApiKey:
    if provider not in PROVIDERS:
        raise KeyError_("Unknown provider.")
    plaintext = plaintext.strip()
    if len(plaintext) < 8:
        raise KeyError_("That key looks too short.")
    row = _live(db, user, provider)
    if row is None:
        # A soft-deleted row for this provider may exist; reuse it so the unique constraint holds.
        row = db.scalar(
            select(UserApiKey).where(UserApiKey.owner_id == user.id, UserApiKey.provider == provider)
        )
        if row is None:
            row = UserApiKey(owner_id=user.id, provider=provider, ciphertext=b"", last4="")
            db.add(row)
    row.deleted_at = None
    row.ciphertext = encrypt_secret(plaintext)
    row.last4 = plaintext[-4:]
    row.last_tested_at = None
    row.last_test_ok = None
    audit.record(db, "api_key.set", actor=user, target_type="user_api_key", target_id=provider)
    db.commit()
    return row


def delete_key(db: Session, user: User, provider: str) -> None:
    row = _live(db, user, provider)
    if row is None:
        raise KeyError_("No key saved for that provider.", 404)
    row.deleted_at = utcnow()
    row.ciphertext = b""  # don't keep a secret we no longer need
    audit.record(db, "api_key.deleted", actor=user, target_type="user_api_key", target_id=provider)
    db.commit()


def reveal_for_server_use(db: Session, user: User, provider: str) -> str | None:
    """Decrypt for an outbound request on the server. Never return this to a client."""
    row = _live(db, user, provider)
    return decrypt_secret(row.ciphertext) if row else None


def test_key(db: Session, user: User, provider: str) -> bool:
    """Stub until Prompt 4 wires the real provider call: a key is 'ok' if it decrypts."""
    row = _live(db, user, provider)
    if row is None:
        raise KeyError_("No key saved for that provider.", 404)
    try:
        ok = len(decrypt_secret(row.ciphertext)) >= 8
    except Exception:
        ok = False
    row.last_tested_at = utcnow()
    row.last_test_ok = ok
    db.commit()
    return ok
