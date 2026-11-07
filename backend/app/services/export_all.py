"""Admin "Export everything" (F5): one zip with a consistent database snapshot, every screenshot and a
manifest, streamed as it is built.

Zip layout:
    db/portal.db                 a consistent copy made with the sqlite3 backup API (deleted afterwards)
    screenshots/<storage key>    every restorable screenshot, full image and thumbnail, as stored
    manifest.json                app version, exported_at, exported_by (display name only), counts per
                                 table, storage backend, SHA-256 of every other file
    README.md                    what this is and how to restore it

The zip members are written one at a time into an unseekable in-memory sink that is drained after every
member (the same approach as services/analytics/export.py), so memory stays at about one screenshot
plus a chunk of the database.
"""

import hashlib
import io
import json
import shutil
import sqlite3
import tempfile
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from .. import __version__
from ..core.settings import get_settings
from ..models import User
from .backup import restorable_screenshots, row_counts, snapshot
from .storage import StorageError, get_storage

CHUNK = 1024 * 1024
# Rows removed from the snapshot copy before it is zipped (never from the live database): sign-in
# sessions, invite links and reset links. Their tokens are stored hashed, so they're useless to an
# attacker anyway, but they're also useless to a restore (everyone signs in again; an admin re-issues any
# open invite), so the export carries none. Password hashes (Argon2id) and the Fernet-encrypted vault stay:
# a restore needs them and neither is readable without the password / TRADING_PORTAL_SECRET_KEY.
OMITTED_TABLES = ("sessions", "password_resets", "invites")

README = """# Trading Portal: export of everything

Made {when} by {who} from Trading Portal {version} (screenshots stored in: {backend}).

- `db/portal.db`: the whole SQLite database, copied consistently with SQLite's backup API while the app
  was running. Open it with any SQLite tool. It holds accounts (password hashes, never passwords), the
  encrypted API-key vault (useless without TRADING_PORTAL_SECRET_KEY), every strategy, session, trade,
  tag, screenshot record, news event and preference.
- `screenshots/…`: every screenshot that is live or still in the 30-day Trash, under the same key the
  `screenshots` table uses (`full_key`, `thumb_key`).
- `manifest.json`: counts per table and a SHA-256 for every file, so you can tell nothing is missing.
- Left out on purpose: sign-in sessions, invite links and password-reset links (`manifest.json` →
  `omitted_tables`). After a restore everyone signs in again and the admin re-issues any open invite.

## To bring it back

1. Stop the app. Put `db/portal.db` at `$TRADING_PORTAL_DATA_DIR/portal.db` (Fly: `/data/portal.db`).
2. Put the `screenshots/` folder next to it (`STORAGE_BACKEND=local`), or upload it to the bucket under
   the `screenshots/` prefix (`STORAGE_BACKEND=s3`; `make migrate-screenshots` does this from a local copy).
3. Start the app; `alembic upgrade head` runs on boot.

Keep this zip somewhere private: it contains the whole journal.
"""


class _Sink(io.RawIOBase):
    """Unseekable buffer zipfile writes into; drained after every member."""

    def __init__(self) -> None:
        self.buf = bytearray()

    def writable(self) -> bool:
        return True

    def write(self, b) -> int:  # type: ignore[override]
        self.buf += b
        return len(b)

    def take(self) -> bytes:
        out = bytes(self.buf)
        self.buf.clear()
        return out


def scrub_snapshot(path: Path) -> None:
    """Delete the OMITTED_TABLES rows from a snapshot copy and VACUUM so the bytes are really gone."""
    conn = sqlite3.connect(path)
    try:
        for table in OMITTED_TABLES:
            conn.execute(f'DELETE FROM "{table}"')
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()


def export_filename(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return f"trading-portal-export-{now:%Y%m%d-%H%M}.zip"


def _info(path: str, *, compress: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=datetime.now(UTC).timetuple()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    info.external_attr = 0o644 << 16
    return info


def stream_everything(db: Session, user: User) -> Iterator[bytes]:
    """Read the screenshot list now; return a generator that snapshots the database and zips.

    The response streams after the request's database session has closed, so nothing lazy may touch it.
    """
    shots = [(s.full_key, s.thumb_key) for s in restorable_screenshots(db)]
    display_name = user.display_name
    settings = get_settings()
    live_db = settings.resolved_data_dir / "portal.db"
    backend = settings.storage_backend

    def generate() -> Iterator[bytes]:
        storage = get_storage()
        sink = _Sink()
        files: list[dict] = []
        missing: list[str] = []
        counts: dict[str, int] = {}
        tmp_dir = Path(tempfile.mkdtemp(prefix="tp-export-"))
        tmp_db = tmp_dir / "portal.db"
        try:
            with zipfile.ZipFile(sink, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                # 1. the database, streamed in chunks from a consistent snapshot
                snapshot(live_db, tmp_db)
                scrub_snapshot(tmp_db)
                counts = row_counts(tmp_db)
                digest, size = hashlib.sha256(), 0
                with zf.open(_info("db/portal.db", compress=True), "w", force_zip64=True) as member:
                    with tmp_db.open("rb") as fh:
                        while chunk := fh.read(CHUNK):
                            member.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
                            yield sink.take()
                files.append({"path": "db/portal.db", "bytes": size, "sha256": digest.hexdigest()})
                tmp_db.unlink()
                yield sink.take()

                # 2. every screenshot, as stored (images are already compressed)
                for full_key, thumb_key in shots:
                    for key in (full_key, thumb_key):
                        path = f"screenshots/{key}"
                        try:
                            data = storage.get(key)
                        except (StorageError, OSError, ValueError):
                            missing.append(path)
                            continue
                        except Exception:  # noqa: BLE001 — an S3 error on one object shouldn't kill the zip
                            missing.append(path)
                            continue
                        zf.writestr(_info(path, compress=False), data)
                        files.append(
                            {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                        )
                        yield sink.take()

                # 3. README and manifest
                when = datetime.now(UTC)
                readme = README.format(
                    when=f"{when:%d %b %Y %H:%M} UTC", who=display_name, version=__version__, backend=backend
                ).encode()
                zf.writestr(_info("README.md", compress=True), readme)
                files.append(
                    {"path": "README.md", "bytes": len(readme), "sha256": hashlib.sha256(readme).hexdigest()}
                )
                manifest = {
                    "app": "Trading Portal",
                    "version": __version__,
                    "format": "trading-portal-export-everything",
                    "format_version": 1,
                    "exported_at": when.isoformat(),
                    "exported_by": display_name,
                    "storage_backend": backend,
                    "counts": counts,
                    "omitted_tables": list(OMITTED_TABLES),
                    "screenshots": {"records": len(shots), "files": 2 * len(shots) - len(missing)},
                    "missing_files": missing,
                    "files": files,
                    "note": "SHA-256 covers every file except this manifest.",
                }
                zf.writestr(_info("manifest.json", compress=True), json.dumps(manifest, indent=2))
            yield sink.take()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)  # the snapshot and any -wal/-shm beside it

    return generate()
