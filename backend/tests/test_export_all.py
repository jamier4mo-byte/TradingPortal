"""Admin "Export everything": a valid streamed zip with a sound DB snapshot, screenshots and a manifest."""

import hashlib
import io
import json
import sqlite3
import zipfile

from sqlalchemy import select

from app.models import AuditLog
from app.services.storage import get_storage
from tests.test_export import strategy_with_shots


def export(client) -> zipfile.ZipFile:
    res = client.get("/api/admin/export")
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/zip"
    assert res.headers["content-disposition"].startswith('attachment; filename="trading-portal-export-')
    assert res.headers["content-disposition"].endswith('.zip"')
    assert res.headers["cache-control"] == "no-store"
    return zipfile.ZipFile(io.BytesIO(res.content))


def test_admin_gets_a_valid_zip(admin_client, db, admin, tmp_path):
    _, _ = strategy_with_shots(admin_client)
    zf = export(admin_client)
    assert zf.testzip() is None
    names = set(zf.namelist())
    assert {"db/portal.db", "manifest.json", "README.md"} <= names
    shots = sorted(n for n in names if n.startswith("screenshots/"))
    assert len(shots) == 6  # 3 slots × (full + thumb)
    assert sum(1 for n in shots if n.endswith(".thumb.webp")) == 3

    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["format"] == "trading-portal-export-everything"
    assert manifest["exported_by"] == "Jamie" and "@" not in json.dumps(manifest)
    assert manifest["storage_backend"] == "local"
    assert manifest["counts"]["users"] == 1 and manifest["counts"]["screenshots"] == 3
    assert manifest["counts"]["trades"] > 0 and "alembic_version" not in manifest["counts"]
    assert manifest["screenshots"] == {"records": 3, "files": 6} and manifest["missing_files"] == []
    listed = {f["path"] for f in manifest["files"]}
    assert listed == names - {"manifest.json"}
    for f in manifest["files"]:
        data = zf.read(f["path"])
        assert len(data) == f["bytes"] and hashlib.sha256(data).hexdigest() == f["sha256"], f["path"]

    # The snapshot is a real database with the schema and the data.
    db_path = tmp_path / "portal.db"
    db_path.write_bytes(zf.read("db/portal.db"))
    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("select count(*) from users").fetchone()[0] == 1
    assert conn.execute("select display_name from users").fetchone()[0] == "Jamie"
    assert conn.execute("select count(*) from screenshots").fetchone()[0] == 3
    conn.close()

    # The screenshot bytes are exactly what the store holds.
    storage = get_storage()
    for n in shots:
        assert zf.read(n) == storage.get(n.removeprefix("screenshots/"))

    assert "export of everything" in zf.read("README.md").decode().lower()
    audit = db.scalars(select(AuditLog).where(AuditLog.action == "export.everything")).all()
    assert len(audit) == 1 and audit[0].actor_id == admin.id


def test_member_forbidden_anon_unauthorised(member_client, client):
    assert member_client.get("/api/admin/export").status_code == 403
    assert client.get("/api/admin/export").status_code == 401


def test_missing_screenshot_file_is_listed_not_fatal(admin_client):
    _, t = strategy_with_shots(admin_client)
    shot = admin_client.get(f"/api/trades/{t['id']}").json()["screenshots"][0]
    storage = get_storage()
    full_key = next(
        k
        for k in (p.relative_to(storage.root).as_posix() for p in storage.root.rglob("*.*"))
        if not k.endswith(".thumb.webp") and f"/{t['id']}/" in f"/{k}"
    )
    storage.delete(full_key)
    zf = export(admin_client)
    assert zf.testzip() is None
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["missing_files"] == [f"screenshots/{full_key}"]
    assert manifest["screenshots"]["files"] == 5
    assert shot["id"]  # the record itself is still in the snapshot


def test_export_with_no_screenshots(admin_client):
    zf = export(admin_client)
    assert zf.testzip() is None
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["screenshots"] == {"records": 0, "files": 0}
    assert {"db/portal.db", "manifest.json", "README.md"} == set(zf.namelist())


def test_snapshot_carries_no_sessions_invites_resets_or_plaintext_secrets(
    admin_client, admin, member, db, tmp_path
):
    """The exporting admin is signed in (a sessions row), has an invite and a reset link open, and a vault
    key saved: the zip must hold none of the ephemeral rows and never the key's plaintext."""
    from app.services import keys as keys_svc

    secret = "tdk-plaintext-should-never-leave-the-server-9f8e7d6c"
    keys_svc.set_key(db, admin, "twelve_data", secret)
    assert admin_client.post("/api/admin/invites", json={"role": "member"}).status_code == 201
    assert admin_client.post(f"/api/admin/users/{member.id}/reset-link").status_code == 201

    zf = export(admin_client)
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["omitted_tables"] == ["sessions", "password_resets", "invites"]
    assert manifest["counts"]["sessions"] == 0
    assert manifest["counts"]["invites"] == 0
    assert manifest["counts"]["password_resets"] == 0
    assert manifest["counts"]["user_api_keys"] == 1  # the encrypted vault row stays (a restore needs it)

    for name in zf.namelist():
        assert secret.encode() not in zf.read(name), name
        assert b"tdk-plaintext" not in zf.read(name), name

    db_path = tmp_path / "scrubbed.db"
    db_path.write_bytes(zf.read("db/portal.db"))
    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    for table in ("sessions", "invites", "password_resets"):
        assert conn.execute(f"select count(*) from {table}").fetchone()[0] == 0, table
    assert conn.execute("select count(*) from users").fetchone()[0] == 2
    assert (
        conn.execute("select password_hash from users where id = ?", (admin.id,))
        .fetchone()[0]
        .startswith("$argon2id$")
    )
    conn.close()

    # The live database is untouched: the admin is still signed in and the links still work.
    assert admin_client.get("/api/auth/me").status_code == 200
    from app.models import Invite, PasswordReset

    assert db.scalar(select(Invite)) is not None and db.scalar(select(PasswordReset)) is not None
