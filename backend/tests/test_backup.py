"""Consistent snapshots, integrity checks, row-count comparison and the `restore-test` CLI (file replica)."""

import os
import sqlite3
import stat

import pytest

from app import cli
from app.core.settings import get_settings
from app.services import backup
from tests.conftest import make_user
from tests.test_journal_api import do_import, new_strategy

LIVE = get_settings().resolved_data_dir / "portal.db"


def _seed(admin_client, db):
    make_user(db, email="alex@example.test", name="Alex")
    s = new_strategy(admin_client)
    do_import(admin_client, s["id"], "backtest")


def test_snapshot_is_consistent_and_sound(admin_client, db, tmp_path):
    _seed(admin_client, db)
    copy = backup.snapshot(LIVE, tmp_path / "snap" / "portal.db")
    assert copy.is_file()
    assert backup.integrity_check(copy) == "ok"
    live, restored = backup.row_counts(LIVE), backup.row_counts(copy)
    assert live == restored
    assert live["users"] == 2 and live["strategies"] == 1 and live["trades"] > 0
    assert "alembic_version" not in live
    report = backup.compare_counts(live, restored)
    assert report.ok and all(mark == "=" for _, _, _, mark in report.rows)
    # A second snapshot to the same path replaces the first.
    backup.snapshot(LIVE, copy)
    assert backup.integrity_check(copy) == "ok"


def test_corrupted_copy_fails_integrity(admin_client, db, tmp_path):
    _seed(admin_client, db)
    copy = backup.snapshot(LIVE, tmp_path / "portal.db")
    size = copy.stat().st_size
    assert size > 4096 * 4
    with copy.open("r+b") as fh:  # wreck the second and third pages
        fh.seek(4096)
        fh.write(b"\xff" * 8192)
    result = backup.integrity_check(copy)
    assert result != "ok" and result


def test_unreadable_file_reports_an_error(tmp_path):
    bad = tmp_path / "not-a-db.db"
    bad.write_bytes(b"hello, this is not sqlite" * 10)
    assert backup.integrity_check(bad).startswith("error:")


def test_compare_counts_marks_volatile_and_mismatched_tables():
    live = {"users": 3, "trades": 10, "sessions": 7, "audit_log": 40, "leases": 1}
    restored = {"users": 3, "trades": 9, "sessions": 5, "audit_log": 38, "price_cache": 2}
    report = backup.compare_counts(live, restored)
    marks = {name: mark for name, _, _, mark in report.rows}
    assert marks["users"] == "="
    assert marks["trades"] == "MISMATCH"
    assert marks["sessions"].startswith("~") and marks["audit_log"].startswith("~")
    assert marks["leases"].startswith("~") and marks["price_cache"].startswith("~")
    assert report.mismatches == ["trades"] and not report.ok
    table = report.table()
    assert "trades" in table and "MISMATCH" in table and "—" in table


# ---- the CLI --------------------------------------------------------------------------------------------


def test_restore_test_cli_from_a_file_replica(admin_client, db, tmp_path, capsys, monkeypatch):
    _seed(admin_client, db)
    monkeypatch.setattr(backup, "litestream_binary", lambda: None)
    replica = tmp_path / "replica"
    backup.snapshot(LIVE, replica / "portal.db")
    out = tmp_path / "out"

    cli.main(["restore-test", "--replica", str(replica), "--out", str(out)])  # exit 0 → returns
    text = capsys.readouterr().out
    assert (out / "portal.db").is_file()
    assert "LOCAL FILE replica" in text and "NOT exercised" in text
    assert "PRAGMA integrity_check: ok" in text
    assert "RESTORE TEST PASSED" in text
    assert "users" in text and "trades" in text

    # The live database moves on (a new user): the counts no longer match and the drill fails.
    make_user(db, email="new@example.test", name="New")
    with pytest.raises(SystemExit) as exc:
        cli.main(["restore-test", "--replica", str(replica), "--out", str(out)])
    assert exc.value.code == 1
    text = capsys.readouterr().out
    assert "RESTORE TEST FAILED" in text and "users" in text and "MISMATCH" in text


def test_restore_test_volatile_tables_may_differ(admin_client, db, tmp_path, monkeypatch):
    _seed(admin_client, db)
    replica = tmp_path / "replica"
    backup.snapshot(LIVE, replica / "portal.db")
    # Another sign-in and an audit row: volatile tables, so still a pass.
    admin_client.post(
        "/api/auth/login", json={"email": "jamie@example.test", "password": "correct-horse-battery"}
    )
    lines: list[str] = []
    code = backup.restore_test(str(replica), tmp_path / "out", echo=lines.append)
    assert code == 0, "\n".join(lines)
    assert any("changes continuously" in line for line in lines)


def test_restore_test_needs_a_replica_or_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "litestream_binary", lambda: None)
    monkeypatch.delenv("BUCKET_NAME", raising=False)
    monkeypatch.delenv("AWS_ENDPOINT_URL_S3", raising=False)
    lines: list[str] = []
    assert backup.restore_test(None, tmp_path / "out", echo=lines.append) == 1
    assert any("No replica" in line for line in lines)
    lines.clear()
    assert backup.restore_test("s3://bucket/litestream/portal.db", tmp_path / "out", echo=lines.append) == 1
    assert any("not on PATH" in line for line in lines)
    lines.clear()
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError):
        backup.restore_test(str(tmp_path / "empty"), tmp_path / "out", echo=lines.append)


def test_configured_replica_url_from_tigris_env(monkeypatch):
    monkeypatch.setenv("BUCKET_NAME", "tp-live")
    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "https://t3.storage.dev")
    assert backup.configured_replica_url() == "s3://tp-live/litestream/portal.db"
    monkeypatch.setenv("BUCKET_NAME", "")
    assert backup.configured_replica_url() is None


def test_restore_test_runs_litestream_when_present(admin_client, db, tmp_path, monkeypatch):
    """A stand-in `litestream` script shows the real path's plumbing: argv, -o, exit code, integrity."""
    _seed(admin_client, db)
    snap = backup.snapshot(LIVE, tmp_path / "snap.db")
    fake = tmp_path / "litestream"
    fake.write_text(
        "#!/bin/sh\n"
        'echo "fake litestream $*"\n'
        "while [ $# -gt 0 ]; do case $1 in -o) OUT=$2; shift 2;; *) shift;; esac; done\n"
        f'cp "{snap}" "$OUT"\n'
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(backup, "litestream_binary", lambda: str(fake))
    lines: list[str] = []
    code = backup.restore_test("s3://tp-live/litestream/portal.db", tmp_path / "out", echo=lines.append)
    assert code == 0, "\n".join(lines)
    assert any("fake litestream restore -o" in line for line in lines)
    assert any("with Litestream" in line for line in lines)
    assert not any("NOT exercised" in line for line in lines)

    failing = tmp_path / "litestream-fail"
    failing.write_text("#!/bin/sh\necho 'no such replica' >&2\nexit 3\n")
    failing.chmod(failing.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(backup, "litestream_binary", lambda: str(failing))
    lines.clear()
    assert backup.restore_test("s3://tp-live/litestream/portal.db", tmp_path / "out", echo=lines.append) == 1
    assert any("exit code 3" in line for line in lines)


def test_snapshot_while_writing_still_opens(admin_client, db, tmp_path):
    """The backup API copies a consistent image even with another connection mid-transaction."""
    _seed(admin_client, db)
    writer = sqlite3.connect(LIVE)
    writer.execute("BEGIN")
    writer.execute("INSERT INTO app_state (key, value, updated_at) VALUES ('t', '{}', '2026-01-01')")
    try:
        copy = backup.snapshot(LIVE, tmp_path / "portal.db")
    finally:
        writer.execute("ROLLBACK")
        writer.close()
    assert backup.integrity_check(copy) == "ok"
    assert backup.row_counts(copy)["app_state"] == 0
    assert os.access(copy, os.R_OK)
