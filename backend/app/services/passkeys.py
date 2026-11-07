"""WebAuthn passkeys via py_webauthn. Challenges live in memory for one process (60 s)."""

import secrets
import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from ..core.security import utcnow
from ..core.settings import get_settings
from ..models import Passkey, User
from . import audit

CHALLENGE_TTL = 60.0


class PasskeyError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class _Challenges:
    def __init__(self) -> None:
        self._items: dict[str, tuple[bytes, float, int | None]] = {}
        self._lock = threading.Lock()

    def put(self, challenge: bytes, user_id: int | None) -> str:
        key = secrets.token_urlsafe(16)
        with self._lock:
            now = time.monotonic()
            self._items = {k: v for k, v in self._items.items() if v[1] > now}
            self._items[key] = (challenge, now + CHALLENGE_TTL, user_id)
        return key

    def pop(self, key: str) -> tuple[bytes, int | None]:
        with self._lock:
            item = self._items.pop(key, None)
        if not item or item[1] < time.monotonic():
            raise PasskeyError("This passkey request timed out. Try again.", 410)
        return item[0], item[2]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


challenges = _Challenges()


def begin_registration(db: Session, user: User) -> tuple[str, str]:
    s = get_settings()
    existing = list(db.scalars(select(Passkey).where(Passkey.user_id == user.id)))
    options = generate_registration_options(
        rp_id=s.rp_id,
        rp_name=s.rp_name,
        user_id=str(user.id).encode(),
        user_name=user.email,
        user_display_name=user.display_name,
        exclude_credentials=[PublicKeyCredentialDescriptor(id=p.credential_id) for p in existing],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    return options_to_json(options), challenges.put(options.challenge, user.id)


def finish_registration(
    db: Session, user: User, *, challenge_key: str, credential: dict, name: str
) -> Passkey:
    s = get_settings()
    challenge, user_id = challenges.pop(challenge_key)
    if user_id != user.id:
        raise PasskeyError("This passkey request belongs to another sign-in.", 403)
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=s.rp_id,
            expected_origin=s.origins,
        )
    except WebAuthnException as exc:
        raise PasskeyError(f"Passkey registration failed: {exc}") from exc
    transports = credential.get("response", {}).get("transports")
    passkey = Passkey(
        user_id=user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        name=(name.strip() or "Passkey")[:80],
        transports=transports if isinstance(transports, list) else None,
        backed_up=bool(verified.credential_backed_up),
        created_at=utcnow(),
    )
    db.add(passkey)
    db.flush()
    audit.record(db, "passkey.registered", actor=user, target_type="passkey", target_id=passkey.id)
    db.commit()
    return passkey


def begin_authentication(db: Session) -> tuple[str, str]:
    """Discoverable-credential flow: no email needed; the authenticator picks the account."""
    options = generate_authentication_options(
        rp_id=get_settings().rp_id, user_verification=UserVerificationRequirement.PREFERRED
    )
    return options_to_json(options), challenges.put(options.challenge, None)


def finish_authentication(db: Session, *, challenge_key: str, credential: dict) -> User:
    s = get_settings()
    challenge, _ = challenges.pop(challenge_key)
    raw_id = credential.get("rawId") or credential.get("id")
    if not isinstance(raw_id, str):
        raise PasskeyError("Malformed passkey response.")
    from webauthn.helpers import base64url_to_bytes

    try:
        credential_id = base64url_to_bytes(raw_id)
    except Exception as exc:  # noqa: BLE001 — binascii / value errors from junk input
        raise PasskeyError("Malformed passkey response.") from exc
    passkey = db.scalar(select(Passkey).where(Passkey.credential_id == credential_id))
    if not passkey:
        raise PasskeyError("That passkey isn't registered here.", 404)
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=s.rp_id,
            expected_origin=s.origins,
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
        )
    except WebAuthnException as exc:
        raise PasskeyError(f"Passkey sign-in failed: {exc}", 401) from exc
    if not passkey.user.is_active:
        raise PasskeyError("This account is deactivated.", 403)
    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = utcnow()
    db.commit()
    return passkey.user


def list_passkeys(db: Session, user: User) -> list[Passkey]:
    return list(db.scalars(select(Passkey).where(Passkey.user_id == user.id).order_by(Passkey.created_at)))


def delete_passkey(db: Session, user: User, passkey_id: int) -> None:
    passkey = db.get(Passkey, passkey_id)
    if not passkey or passkey.user_id != user.id:
        raise PasskeyError("Passkey not found.", 404)
    db.delete(passkey)
    audit.record(db, "passkey.deleted", actor=user, target_type="passkey", target_id=passkey_id)
    db.commit()
