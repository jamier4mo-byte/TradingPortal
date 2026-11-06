"""News tags on trades (3.6): inside a news window, outside, or no news data.

`trades.news_impact`:
  "high"  the entry time (`opened_at`) is within ± the trade owner's `news_window_minutes` of a
          high-impact event whose currency maps to the trade's instrument (news_instrument_map)
  "none"  outside every window, and the trade's UK market date is inside news_history_coverage
  NULL    no news data: the date is outside coverage, so we don't guess (F4)
`trades.news_events`: [{event_id, name, currency, at, minutes_from_entry}] where minutes_from_entry is
the event time minus the entry time, in whole minutes (negative: the event came before the entry).

Re-tagging happens on trade create/import/edit, on a window or mapping change, and from the scheduler
when the coverage fingerprint changes (`retag_if_coverage_grew`).
"""

import bisect
import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only

from ...models import AppState, Event, EventType, Trade, UserMarketPrefs
from ..market_prefs import DEFAULT_WINDOW_MINUTES, MAX_WINDOW_MINUTES, instrument_map
from . import store

STATE_KEY = "news_tagging"
_TRADE_COLUMNS = (
    Trade.id,
    Trade.owner_id,
    Trade.instrument,
    Trade.opened_at,
    Trade.market_date,
    Trade.news_impact,
    Trade.news_events,
)


def _iso(dt: datetime) -> str:
    return store.utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


class Tagger:
    """Everything tagging needs, loaded once for a batch of trades."""

    def __init__(self, db: Session, lo: datetime, hi: datetime) -> None:
        self.ranges = store.coverage_ranges(db)
        self.currencies: dict[str, set[str]] = {}
        for cur, instruments in instrument_map(db).items():
            for inst in instruments:
                self.currencies.setdefault(inst, set()).add(cur)
        prefs = select(UserMarketPrefs.user_id, UserMarketPrefs.news_window_minutes)
        self.windows: dict[int, int] = {uid: w for uid, w in db.execute(prefs)}
        pad = timedelta(minutes=MAX_WINDOW_MINUTES)
        rows = db.execute(
            select(Event.id, Event.at, Event.currency, Event.title, EventType.name)
            .outerjoin(EventType, EventType.id == Event.event_type_id)
            .where(Event.impact == "high", Event.at >= lo - pad, Event.at <= hi + pad)
            .order_by(Event.at)
        ).all()
        self.events = [(store.utc(r.at), r) for r in rows]
        self.times = [at for at, _ in self.events]

    def tag(
        self, opened_at: datetime, instrument: str, owner_id: int, market_date
    ) -> tuple[str | None, list | None]:
        opened = store.utc(opened_at)
        window = timedelta(minutes=self.windows.get(owner_id, DEFAULT_WINDOW_MINUTES))
        wanted = self.currencies.get((instrument or "").upper(), set())
        hits: list[dict] = []
        if wanted:
            i = bisect.bisect_left(self.times, opened - window)
            while i < len(self.events) and self.times[i] <= opened + window:
                at, r = self.events[i]
                if r.currency.upper() in wanted:
                    hits.append(
                        {
                            "event_id": r.id,
                            "name": r.name or r.title,
                            "currency": r.currency,
                            "at": _iso(at),
                            "minutes_from_entry": round((at - opened).total_seconds() / 60),
                        }
                    )
                i += 1
        if hits:
            return "high", hits
        day = market_date or store.uk_date(opened)
        if store.covered(self.ranges, day):
            return "none", []
        return None, None


def tag_trades(db: Session, trades: Iterable[Trade]) -> int:
    """Tag these ORM trades in place (no commit). Returns how many changed."""
    trades = [t for t in trades if t.opened_at is not None]
    if not trades:
        return 0
    opens = [store.utc(t.opened_at) for t in trades]
    tagger = Tagger(db, min(opens), max(opens))
    changed = 0
    for t in trades:
        impact, events = tagger.tag(t.opened_at, t.instrument, t.owner_id, t.market_date)
        if t.news_impact != impact or t.news_events != events:
            t.news_impact, t.news_events = impact, events
            changed += 1
    db.flush()
    return changed


def retag(db: Session, *, user_id: int | None = None) -> int:
    """Re-tag every trade (or one owner's), deleted ones included so a restore is already right. Commits."""
    stmt = select(Trade).options(load_only(*_TRADE_COLUMNS))
    if user_id is not None:
        stmt = stmt.where(Trade.owner_id == user_id)
    changed = 0
    trades = list(db.scalars(stmt))
    for i in range(0, len(trades), 2000):
        changed += tag_trades(db, trades[i : i + 2000])
    db.commit()
    return changed


def fingerprint(db: Session) -> str:
    """Coverage plus a summary of the high-impact events: changes whenever a tag could change."""
    ranges = store.coverage_ranges(db)
    summary = select(func.count(Event.id), func.max(Event.at), func.max(Event.updated_at))
    n, last_at, last_upd = db.execute(summary.where(Event.impact == "high")).one()
    raw = json.dumps([[a.isoformat(), b.isoformat()] for a, b in ranges] + [n, str(last_at), str(last_upd)])
    return hashlib.sha1(raw.encode()).hexdigest()


def retag_if_coverage_grew(db: Session, now: datetime) -> dict:
    """Scheduler job: re-tag all trades when coverage (or the high-impact events) changed. Cheap otherwise."""
    fp = fingerprint(db)
    state = db.get(AppState, STATE_KEY)
    if state is not None and (state.value or {}).get("fingerprint") == fp:
        return {"retagged": 0}
    changed = retag(db)
    state = db.get(AppState, STATE_KEY)
    value = {"fingerprint": fp, "at": _iso(now or datetime.now(UTC)), "changed": changed}
    if state is None:
        db.add(AppState(key=STATE_KEY, value=value))
    else:
        state.value = value
    db.commit()
    return {"retagged": changed}
