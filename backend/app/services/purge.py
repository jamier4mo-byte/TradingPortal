"""Trash purge (F5): records soft-deleted more than TRASH_DAYS ago are removed for good, once a day.

Order matters for the foreign keys: screenshots (and their stored files) → trade_tags → trades →
journal_sessions → strategies. A strategy in the Trash takes its sessions, trades and screenshots with
it even if those were never deleted on their own; a live trade whose session is purged just loses
the session link (session_id is nullable) rather than disappearing.

PURGE_TARGETS can be extended by other modules (e.g. calendar tasks): any model added that is not one
of the four journal models is purged with a plain `DELETE … WHERE deleted_at < cutoff`.
"""

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..models import AppState, JournalSession, Screenshot, Strategy, Trade, trade_tags, utcnow
from .journal import TRASH_DAYS
from .storage import Storage, StorageError, get_storage

log = logging.getLogger("trading_portal.purge")

UK = ZoneInfo("Europe/London")
LAST_RUN_KEY = "purge.last_run"
PURGE_TARGETS: list[type] = [Screenshot, Trade, JournalSession, Strategy]
_JOURNAL = (Screenshot, Trade, JournalSession, Strategy)


def _delete_files(storage: Storage, shot: Screenshot) -> int:
    """Both objects of a screenshot; a missing or failing object never stops the purge."""
    failures = 0
    for key in (shot.full_key, shot.thumb_key):
        try:
            storage.delete(key)
        except (StorageError, OSError) as exc:
            failures += 1
            log.warning("purge: could not delete %s: %s", key, exc)
        except Exception as exc:  # noqa: BLE001 — e.g. a boto3 ClientError; keep purging
            failures += 1
            log.warning("purge: could not delete %s: %s", key, exc)
    return failures


def purge_trash(db: Session, now: datetime | None = None, storage: Storage | None = None) -> dict:
    """Remove everything soft-deleted before now − TRASH_DAYS. Returns counts per table."""
    now = now or utcnow()
    cutoff = now - timedelta(days=TRASH_DAYS)
    storage = storage or get_storage()
    result = {
        "cutoff": cutoff.isoformat(),
        "screenshots": 0,
        "trades": 0,
        "journal_sessions": 0,
        "strategies": 0,
        "files_failed": 0,
        "sessions_unlinked": 0,
    }

    strategy_ids = set(
        db.scalars(select(Strategy.id).where(Strategy.deleted_at.is_not(None), Strategy.deleted_at < cutoff))
    )
    session_stmt = select(JournalSession.id).where(
        (JournalSession.deleted_at.is_not(None) & (JournalSession.deleted_at < cutoff))
        | JournalSession.strategy_id.in_(strategy_ids)
    )
    session_ids = set(db.scalars(session_stmt))
    trade_stmt = select(Trade.id).where(
        (Trade.deleted_at.is_not(None) & (Trade.deleted_at < cutoff)) | Trade.strategy_id.in_(strategy_ids)
    )
    trade_ids = set(db.scalars(trade_stmt))
    shot_stmt = select(Screenshot).where(
        (Screenshot.deleted_at.is_not(None) & (Screenshot.deleted_at < cutoff))
        | Screenshot.trade_id.in_(trade_ids)
    )
    shots = list(db.scalars(shot_stmt))

    for shot in shots:
        result["files_failed"] += _delete_files(storage, shot)
    if shots:
        db.execute(delete(Screenshot).where(Screenshot.id.in_([s.id for s in shots])))
        result["screenshots"] = len(shots)
    if trade_ids:
        db.execute(delete(trade_tags).where(trade_tags.c.trade_id.in_(trade_ids)))
        db.execute(delete(Trade).where(Trade.id.in_(trade_ids)))
        result["trades"] = len(trade_ids)
    if session_ids:
        unlinked = db.execute(update(Trade).where(Trade.session_id.in_(session_ids)).values(session_id=None))
        result["sessions_unlinked"] = unlinked.rowcount or 0
        db.execute(delete(JournalSession).where(JournalSession.id.in_(session_ids)))
        result["journal_sessions"] = len(session_ids)
    if strategy_ids:
        db.execute(delete(Strategy).where(Strategy.id.in_(strategy_ids)))
        result["strategies"] = len(strategy_ids)

    for model in PURGE_TARGETS:
        if model in _JOURNAL:
            continue
        deleted_at = getattr(model, "deleted_at", None)
        if deleted_at is None:
            continue
        res = db.execute(delete(model).where(deleted_at.is_not(None), deleted_at < cutoff))
        result[model.__tablename__] = res.rowcount or 0

    db.commit()
    if any(v for k, v in result.items() if k not in ("cutoff", "files_failed", "sessions_unlinked")):
        log.info("purge: %s", result)
    return result


def _uk_date(now: datetime) -> date:
    return now.astimezone(UK).date()


def run(db: Session, now: datetime | None = None) -> dict | None:
    """Scheduler job: purge once per UK calendar day; `purge.last_run` in app_state remembers the date."""
    now = now or utcnow()
    today = _uk_date(now).isoformat()
    state = db.get(AppState, LAST_RUN_KEY)
    if state and state.value.get("date") == today:
        return None
    result = purge_trash(db, now)
    if state is None:
        state = AppState(key=LAST_RUN_KEY, value={})
        db.add(state)
    state.value = {"date": today, "at": now.isoformat(), "result": result}
    db.commit()
    return result
