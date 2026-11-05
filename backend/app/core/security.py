"""Password hashing, opaque tokens, CSRF and the Fernet vault key.

Plaintext tokens are shown once and only their SHA-256 is stored. A plaintext API key never
leaves the server: it is Fernet-encrypted with a key derived from the secret key.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .settings import get_settings

_hasher = PasswordHasher()  # Argon2id, library defaults (OWASP-recommended)
# Verified when the email is unknown, so a missing account costs the same time as a wrong password.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

MIN_PASSWORD_LENGTH = 10


def utcnow() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except VerifyMismatchError:
        return False
    except Exception:  # malformed hash
        return False


def password_problem(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters."
    if password != password.strip():
        return "No spaces at the start or end."
    return None


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_match(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


@lru_cache
def _fernet() -> Fernet:
    secret = get_settings().require_secret_key().encode()
    derived = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"trading-portal/api-key-vault"
    ).derive(secret)
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt_secret(ciphertext: bytes) -> str:
    return _fernet().decrypt(ciphertext).decode()
