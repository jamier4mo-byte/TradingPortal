"""Settings, secret-key rules, the vault cipher, model mixins and the audit log."""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.core import security
from app.core.settings import Settings
from app.models import AuditLog, UserApiKey


def test_production_refuses_to_start_without_secret_key(tmp_path: Path) -> None:
    s = Settings(env="production", data_dir=tmp_path, secret_key=None, _env_file=None)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        s.require_secret_key()
    s = Settings(env="production", data_dir=tmp_path, secret_key="short", _env_file=None)
    with pytest.raises(RuntimeError, match="32"):
        s.require_secret_key()
    s = Settings(env="production", data_dir=tmp_path, secret_key="x" * 40, _env_file=None)
    assert s.require_secret_key() == "x" * 40
    assert s.cookie_secure is True


def test_development_persists_a_dev_key_outside_the_repo(tmp_path: Path) -> None:
    s = Settings(env="development", data_dir=tmp_path, secret_key=None, _env_file=None)
    key = s.require_secret_key()
    assert len(key) >= 32
    assert (tmp_path / ".dev-secret-key").read_text().strip() == key
    assert s.require_secret_key() == key  # stable across restarts
    assert s.cookie_secure is False


def test_password_hashing_is_argon2id_and_rejects_bad_hashes() -> None:
    h = security.hash_password("a-long-password")
    assert h.startswith("$argon2id$")
    assert security.verify_password("a-long-password", h)
    assert not security.verify_password("wrong-password", h)
    assert not security.verify_password("anything", None)
    assert not security.verify_password("anything", "garbage")


def test_password_rules() -> None:
    assert security.password_problem("short") is not None
    assert security.password_problem(" padded-password") is not None
    assert security.password_problem("long-enough-ok") is None


def test_tokens_are_stored_hashed_only() -> None:
    t = security.new_token()
    assert len(t) >= 40
    assert security.hash_token(t) != t and len(security.hash_token(t)) == 64


def test_vault_round_trip() -> None:
    ct = security.encrypt_secret("hello-secret")
    assert b"hello-secret" not in ct
    assert security.decrypt_secret(ct) == "hello-secret"


def test_owned_records_have_the_shared_columns() -> None:
    cols = {c.name for c in UserApiKey.__table__.columns}
    assert {"owner_id", "created_at", "updated_at", "deleted_at"} <= cols


def test_audit_log_records_login_and_admin_actions(admin_client, member, db) -> None:
    admin_client.patch(f"/api/admin/users/{member.id}/role", json={"role": "admin"})
    actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.at))]
    assert "auth.login" in actions and "user.role_changed" in actions
    row = db.scalar(select(AuditLog).where(AuditLog.action == "user.role_changed"))
    assert row.target_type == "user" and row.target_id == str(member.id) and row.meta == {"role": "admin"}
