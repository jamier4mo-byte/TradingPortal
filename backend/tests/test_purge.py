"""Trash purge: 30-day rule, cascade from a trashed strategy, storage files, once a day, missing files."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import AppState, JournalSession, Screenshot, Strategy, Tag, Trade, trade_tags
from app.services import purge, scheduler
from app.services.storage import LocalStorage, StorageError, get_storage
from tests.conftest import make_user

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)
OLD = NOW - timedelta(days=31)
RECENT = NOW - timedelta(days=29)
PURGE_JOB = [("trash.purge", "app.services.purge:run")]


@pytest.fixture
def owner(db):
    return make_user(db, email="jamie@example.test", role="admin", name="Jamie")


def strategy(db, owner, deleted_at=None) -> Strategy:
    s = Strategy(owner_id=owner.id, name="S", deleted_at=deleted_at)
    db.add(s)
    db.flush()
    return s


def session(db, s: Strategy, deleted_at=None) -> JournalSession:
    js = JournalSession(
        owner_id=s.owner_id,
        strategy_id=s.id,
        kind="backtest",
        csv_timezone="Europe/London",
        deleted_at=deleted_at,
    )
    db.add(js)
    db.flush()
    return js


def trade(db, s: Strategy, deleted_at=None, js: JournalSession | None = None, tagged=True) -> Trade:
    t = Trade(
        owner_id=s.owner_id,
        strategy_id=s.id,
        session_id=js.id if js else None,
        kind="backtest",
        instrument="NAS100",
        side="buy",
        opened_at=NOW - timedelta(days=60),
        market_date=date(2026, 9, 7),
        deleted_at=deleted_at,
    )
    if tagged:
        t.tags = [db.scalar(select(Tag).order_by(Tag.id).limit(1))]
    db.add(t)
    db.flush()
    return t


_counter = iter(range(1, 10_000))


def screenshot(db, t: Trade, deleted_at=None, with_files=True) -> Screenshot:
    base = f"{t.strategy_id}/{t.id}/entry-{next(_counter):08x}"  # unique per screenshot, as the app does
    shot = Screenshot(
        owner_id=t.owner_id,
        trade_id=t.id,
        slot="entry",
        full_key=f"{base}.png",
        thumb_key=f"{base}.thumb.webp",
        width=10,
        height=10,
        bytes=3,
        content_type="image/png",
        deleted_at=deleted_at,
    )
    if with_files:
        storage = get_storage()
        storage.put(shot.full_key, b"png", "image/png")
        storage.put(shot.thumb_key, b"webp", "image/webp")
    db.add(shot)
    db.flush()
    return shot


def ids(db, model) -> set[int]:
    db.expire_all()
    return set(db.scalars(select(model.id)))


def tag_rows(db, trade_id: int) -> int:
    return len(db.execute(select(trade_tags).where(trade_tags.c.trade_id == trade_id)).all())


def test_old_trash_goes_recent_trash_and_live_stay(db, owner):
    s = strategy(db, owner)
    live = trade(db, s)
    recent = trade(db, s, deleted_at=RECENT)
    old = trade(db, s, deleted_at=OLD)
    live_shot, recent_shot, old_shot = screenshot(db, live), screenshot(db, recent), screenshot(db, old)
    old_shot_on_live = screenshot(db, live, deleted_at=OLD)  # a replaced screenshot on a live trade
    db.commit()
    storage = get_storage()

    result = purge.purge_trash(db, NOW)

    assert result["trades"] == 1 and result["screenshots"] == 2 and result["strategies"] == 0
    assert ids(db, Trade) == {live.id, recent.id}
    assert ids(db, Screenshot) == {live_shot.id, recent_shot.id}
    assert tag_rows(db, old.id) == 0 and tag_rows(db, live.id) == 1 and tag_rows(db, recent.id) == 1
    for shot in (old_shot, old_shot_on_live):
        assert not storage.exists(shot.full_key) and not storage.exists(shot.thumb_key)
    for shot in (live_shot, recent_shot):
        assert storage.exists(shot.full_key) and storage.exists(shot.thumb_key)


def test_trashed_strategy_takes_its_children(db, owner):
    gone = strategy(db, owner, deleted_at=OLD)
    js = session(db, gone)
    t1, t2 = trade(db, gone, js=js), trade(db, gone)  # never deleted on their own
    shot = screenshot(db, t1)
    keep = strategy(db, owner, deleted_at=RECENT)
    keep_js = session(db, keep)
    keep_t = trade(db, keep, js=keep_js)
    db.commit()

    result = purge.purge_trash(db, NOW)

    assert result == {
        **result,
        "strategies": 1,
        "journal_sessions": 1,
        "trades": 2,
        "screenshots": 1,
        "files_failed": 0,
    }
    assert ids(db, Strategy) == {keep.id}
    assert ids(db, JournalSession) == {keep_js.id}
    assert ids(db, Trade) == {keep_t.id}
    assert ids(db, Screenshot) == set()
    assert not get_storage().exists(shot.full_key)
    assert t1.id not in ids(db, Trade) and t2.id not in ids(db, Trade)


def test_purged_session_unlinks_a_restored_trade(db, owner):
    """Undo session trashed the session and its trades; one trade was restored on its own later."""
    s = strategy(db, owner)
    js = session(db, s, deleted_at=OLD)
    restored = trade(db, s, js=js)  # live again
    also_gone = trade(db, s, js=js, deleted_at=OLD)
    db.commit()

    result = purge.purge_trash(db, NOW)

    assert result["journal_sessions"] == 1 and result["trades"] == 1 and result["sessions_unlinked"] == 1
    db.expire_all()
    assert db.get(Trade, restored.id).session_id is None
    assert db.get(Trade, also_gone.id) is None
    assert db.get(JournalSession, js.id) is None


def test_missing_or_failing_storage_objects_do_not_stop_the_purge(db, owner, tmp_path):
    s = strategy(db, owner)
    t = trade(db, s, deleted_at=OLD)
    no_files = screenshot(db, t, with_files=False)
    with_files = screenshot(db, t)
    db.commit()

    class Flaky(LocalStorage):
        def delete(self, key: str) -> None:
            if key == with_files.full_key:
                raise StorageError("bucket unreachable")
            super().delete(key)

    flaky = Flaky(get_storage().root)
    result = purge.purge_trash(db, NOW, storage=flaky)
    assert result["screenshots"] == 2 and result["trades"] == 1
    assert result["files_failed"] == 1  # the one that raised; missing files are not failures
    assert ids(db, Screenshot) == set() and no_files.id not in ids(db, Screenshot)
    assert not flaky.exists(with_files.thumb_key)


def test_nothing_to_do_is_quiet(db, owner):
    s = strategy(db, owner)
    trade(db, s)
    db.commit()
    result = purge.purge_trash(db, NOW)
    assert result["trades"] == 0 and result["screenshots"] == 0
    assert ids(db, Trade) != set()


def test_job_runs_once_per_uk_day(db, owner):
    s = strategy(db, owner)
    trade(db, s, deleted_at=OLD)
    db.commit()

    first = purge.run(db, NOW)
    assert first is not None and first["trades"] == 1
    state = db.get(AppState, purge.LAST_RUN_KEY)
    assert state.value["date"] == "2026-11-06" and state.value["result"]["trades"] == 1

    trade(db, s, deleted_at=OLD)
    db.commit()
    assert purge.run(db, NOW + timedelta(hours=5)) is None  # same day: nothing
    assert len(ids(db, Trade)) == 1

    # 23:30 UTC on 6 Nov is still 6 Nov in the UK (GMT); 00:30 UTC on the 7th is a new day.
    assert purge.run(db, datetime(2026, 11, 6, 23, 30, tzinfo=UTC)) is None
    again = purge.run(db, datetime(2026, 11, 7, 0, 30, tzinfo=UTC))
    assert again is not None and again["trades"] == 1
    assert ids(db, Trade) == set()
    db.expire_all()
    assert db.get(AppState, purge.LAST_RUN_KEY).value["date"] == "2026-11-07"


def test_scheduler_runs_the_purge_job(db, owner):
    assert ("trash.purge", "app.services.purge:run") in scheduler.JOBS
    s = strategy(db, owner)
    trade(db, s, deleted_at=OLD)
    db.commit()
    out = scheduler.tick(db, now=NOW, holder="proc-test", jobs=PURGE_JOB)
    assert out["trash.purge"]["trades"] == 1
    assert scheduler.tick(db, now=NOW + timedelta(minutes=1), holder="proc-test", jobs=PURGE_JOB) == {
        "trash.purge": None
    }


def test_purge_targets_can_be_extended(db, owner, monkeypatch):
    """A model appended later (e.g. calendar tasks) is purged with the plain deleted_at rule."""
    from app.models import Instrument, UserApiKey

    monkeypatch.setattr(purge, "PURGE_TARGETS", [*purge.PURGE_TARGETS, UserApiKey, Instrument])
    s = strategy(db, owner)
    trade(db, s, deleted_at=OLD)
    db.commit()
    result = purge.purge_trash(db, NOW)
    assert result["trades"] == 1
    assert result["user_api_keys"] == 0  # soft-deletable: handled by the generic rule
    assert "instruments" not in result  # no deleted_at column: skipped, never crashes
