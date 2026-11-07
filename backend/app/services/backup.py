"""Data safety (F5): consistent SQLite snapshots, integrity checks, the restore drill and the
local → S3 screenshot migration.

Litestream streams the live database to Tigris; this module is everything around it that is plain
Python: `snapshot()` uses the sqlite3 backup API, so a copy taken while the app is writing is still a
consistent database; `restore_test()` is what `make restore-test` runs (quarterly, see
docs/ops/RESTORE-TEST.md); `copy_screenshots()` is `make migrate-screenshots`.
"""

import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.settings import get_settings
from ..models import Screenshot, utcnow
from .journal import TRASH_DAYS
from .storage import Storage, local_storage

# Tables that change on their own while the app runs (sign-ins, leases, job cursors, logs, caches),
# so their counts are reported but never fail the restore test.
VOLATILE_TABLES = frozenset(
    {"sessions", "leases", "app_state", "audit_log", "price_cache", "feed_runs", "alert_deliveries"}
)
DEFAULT_OUT = Path("/tmp/tp-restore-test")
LITESTREAM_DB_PATH = "litestream/portal.db"  # the replica path in litestream.yml


# ---- snapshots and checks -----------------------------------------------------------------------------


def snapshot(src_db_path: Path | str, dest_path: Path | str) -> Path:
    """Copy a live SQLite database consistently (the online backup API, page by page, WAL included)."""
    src, dest = Path(src_db_path), Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    with sqlite3.connect(f"file:{src}?mode=ro", uri=True) as source, sqlite3.connect(dest) as target:
        source.backup(target)
    target.close()
    source.close()
    return dest


def integrity_check(path: Path | str) -> str:
    """`PRAGMA integrity_check`: "ok" when the file is sound, else the first problems SQLite reports."""
    conn = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)
    try:
        rows = conn.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.DatabaseError as exc:  # e.g. "file is not a database" when the header is wrecked
        return f"error: {exc}"
    finally:
        conn.close()
    return "\n".join(str(r[0]) for r in rows) if rows else "no result"


def row_counts(path: Path | str) -> dict[str, int]:
    """Rows per user table, sorted by name. Alembic's version table is left out."""
    with sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True) as conn:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "AND name <> 'alembic_version' ORDER BY name"
            )
        ]
        counts = {n: conn.execute(f'SELECT count(*) FROM "{n}"').fetchone()[0] for n in names}
    conn.close()
    return counts


@dataclass
class CountReport:
    # (table, live count, restored count, mark)
    rows: list[tuple[str, int | None, int | None, str]] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)  # tables that differ and are not volatile

    @property
    def ok(self) -> bool:
        return not self.mismatches

    def table(self) -> str:
        width = max([len("table")] + [len(r[0]) for r in self.rows])
        lines = [
            f"{'table':<{width}}  {'live':>8}  {'restored':>8}  ",
            f"{'-' * width}  {'-' * 8}  {'-' * 8}  ",
        ]
        for name, live, restored, mark in self.rows:
            lines.append(f"{name:<{width}}  {_n(live):>8}  {_n(restored):>8}  {mark}")
        return "\n".join(lines)


def _n(v: int | None) -> str:
    return "—" if v is None else str(v)


def compare_counts(live: dict[str, int], restored: dict[str, int]) -> CountReport:
    """Every table in either database. Equal → "=", volatile and different → "~ (changes continuously)",
    anything else different → "MISMATCH"."""
    report = CountReport()
    for name in sorted(set(live) | set(restored)):
        a, b = live.get(name), restored.get(name)
        if a == b:
            mark = "="
        elif name in VOLATILE_TABLES:
            mark = "~ changes continuously"
        else:
            mark = "MISMATCH"
            report.mismatches.append(name)
        report.rows.append((name, a, b, mark))
    return report


# ---- the restore drill ------------------------------------------------------------------------------


def litestream_binary() -> str | None:
    return shutil.which("litestream")


def configured_replica_url() -> str | None:
    """s3://BUCKET/litestream/portal.db when the Tigris env is present (what litestream.yml reads too)."""
    bucket = os.environ.get("BUCKET_NAME", "").strip()
    endpoint = os.environ.get("AWS_ENDPOINT_URL_S3", "").strip()
    if bucket and endpoint:
        return f"s3://{bucket}/{LITESTREAM_DB_PATH}"
    return None


def _restore_from_directory(replica_dir: Path, dest: Path) -> str:
    """The fallback replica: a directory holding a snapshot made by `snapshot()` (portal.db or any *.db)."""
    candidates = [replica_dir / "portal.db"] + sorted(replica_dir.glob("*.db"))
    source = next((c for c in candidates if c.is_file()), None)
    if source is None:
        raise FileNotFoundError(f"No .db file in {replica_dir}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    return str(source)


def restore_test(
    replica: str | None = None,
    out: Path | str = DEFAULT_OUT,
    *,
    live_db: Path | str | None = None,
    echo=print,
) -> int:
    """Restore the replica into `out`, check integrity, compare counts with the live database.

    Returns 0 when the restored file is sound and every non-volatile table matches, 1 otherwise.
    Real Litestream restore when the binary is on PATH and `replica` is a URL (or the Tigris env is set);
    otherwise `replica` must be a directory holding a snapshot, and we say so loudly.
    """
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    restored = out_dir / "portal.db"
    for stale in (restored, restored.with_name("portal.db-wal"), restored.with_name("portal.db-shm")):
        if stale.exists():
            stale.unlink()
    live = Path(live_db) if live_db else get_settings().resolved_data_dir / "portal.db"
    binary = litestream_binary()
    replica = replica or configured_replica_url()
    if not replica:
        echo("No replica: pass --replica <s3 url or directory>, or set BUCKET_NAME and AWS_ENDPOINT_URL_S3.")
        return 1

    if Path(replica).is_dir():
        source = _restore_from_directory(Path(replica), restored)
        echo(f"Restored from the LOCAL FILE replica {source}.")
        echo("NOTE: the real Litestream restore was NOT exercised (no S3 replica or no litestream binary).")
    elif binary:
        cmd = [binary, "restore", "-o", str(restored), replica]
        echo("$ " + " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.stdout.strip():
            echo(proc.stdout.rstrip())
        if proc.returncode != 0:
            echo(proc.stderr.rstrip())
            echo(f"litestream restore failed with exit code {proc.returncode}.")
            return 1
        echo(f"Restored {replica} with Litestream.")
    else:
        echo(f"{replica} looks like a replica URL but `litestream` is not on PATH.")
        echo("Install Litestream (https://litestream.io/install) or pass --replica <dir with a snapshot>.")
        return 1

    if not restored.is_file():
        echo(f"Nothing was restored to {restored}.")
        return 1
    check = integrity_check(restored)
    echo(f"\nPRAGMA integrity_check: {check}")
    if check != "ok":
        return 1
    if not live.is_file():
        echo(f"\nLive database not found at {live}; counts of the restored copy only:")
        for name, n in row_counts(restored).items():
            echo(f"  {name:<28} {n:>8}")
        return 0
    report = compare_counts(row_counts(live), row_counts(restored))
    echo(f"\nRow counts: live {live} vs restored {restored}")
    echo(report.table())
    echo(
        "\n'~' tables (sessions, leases, app_state, audit_log, price_cache, …) change continuously and "
        "are allowed to differ."
    )
    if report.ok:
        echo("\nRESTORE TEST PASSED: integrity ok and every other table matches.")
        return 0
    echo(f"\nRESTORE TEST FAILED: counts differ in {', '.join(report.mismatches)}.")
    return 1


# ---- screenshots local → S3 -------------------------------------------------------------------------


def restorable_screenshots(db: Session):
    """Live rows plus ones still in the 30-day Trash (they can be restored, so their files must exist)."""
    cutoff = utcnow() - timedelta(days=TRASH_DAYS)
    return db.scalars(
        select(Screenshot).where((Screenshot.deleted_at.is_(None)) | (Screenshot.deleted_at >= cutoff))
    )


def copy_screenshots(
    db: Session, src: Storage, dst: Storage, *, dry_run: bool = False, echo=print
) -> dict[str, int]:
    """Copy every screenshot's full image and thumbnail from `src` to `dst` unless `dst` already has it.

    Idempotent and resumable (the exists check); never deletes anything in `src`.
    """
    counts = {"copied": 0, "skipped": 0, "missing": 0}
    for shot in restorable_screenshots(db):
        for key, ctype in ((shot.full_key, shot.content_type), (shot.thumb_key, "image/webp")):
            if dst.exists(key):
                counts["skipped"] += 1
                continue
            if not src.exists(key):
                counts["missing"] += 1
                echo(f"missing locally: {key}")
                continue
            if not dry_run:
                dst.put(key, src.get(key), ctype)
            counts["copied"] += 1
    verb = "would copy" if dry_run else "copied"
    echo(
        f"{verb} {counts['copied']}, skipped {counts['skipped']} (already there), missing {counts['missing']}"
    )
    return counts


def migrate_screenshots(db: Session, *, dry_run: bool = False, echo=print) -> dict[str, int]:
    """`make migrate-screenshots`: the data-dir files → the configured S3 bucket."""
    from .storage import S3Storage, get_storage

    dst = get_storage()
    if not isinstance(dst, S3Storage):
        raise RuntimeError("STORAGE_BACKEND is not s3: nothing to migrate to. Set it and BUCKET_NAME first.")
    return copy_screenshots(db, local_storage(), dst, dry_run=dry_run, echo=echo)
