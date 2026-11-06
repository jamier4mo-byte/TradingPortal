"""Upserts from both feeds into `events`, the Forex Factory + JBlanked merge, and history coverage.

One release is one row. Forex Factory has no ids, so its key is a hash of currency + normalised title +
UK date (a time change on the same day updates the row instead of duplicating it). JBlanked rows key on
"{Event_ID or slug}:{UTC time}". A JBlanked row merges into a Forex Factory row (and vice versa) when the
currency matches, the event type (or normalised title) matches, the UK date matches and the times are
within 90 minutes.
"""

import hashlib
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...models import Event, FeedRun, NewsHistoryCoverage, PriceReaction
from ..journal_rules import to_uk
from . import catalogue
from .parse import parse_figure, parse_value, style_like

MERGE_MINUTES = 90
FF, JB = "forex_factory", "jblanked"


def utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def uk_date(dt: datetime) -> date:
    return to_uk(utc(dt)).date()


def ff_key(currency: str, title: str, at: datetime, n: int = 1) -> str:
    base = f"{currency.upper()}|{catalogue.normalise(title)}|{uk_date(at).isoformat()}"
    if n > 1:
        base += f"#{n}"
    return hashlib.sha1(base.encode()).hexdigest()


def jb_key(event_id: int | None, title: str, at: datetime) -> str:
    ident = str(event_id) if event_id else catalogue.slug(title)[:40]
    return f"{ident}:{utc(at).strftime('%Y-%m-%dT%H:%MZ')}"


def _set(ev: Event, field: str, value) -> bool:
    if getattr(ev, field) != value:
        setattr(ev, field, value)
        return True
    return False


def _add_source(ev: Event, source: str) -> bool:
    if source in (ev.sources or []):
        return False
    ev.sources = [*(ev.sources or []), source]
    return True


def find_partner(
    db: Session, currency: str, event_type_id: int | None, title: str, at: datetime, *, missing: str
) -> Event | None:
    """The other feed's row for the same release (`missing` names the key column that must be empty)."""
    at = utc(at)
    col = Event.ff_key if missing == "ff_key" else Event.jb_key
    candidates = db.scalars(
        select(Event).where(
            Event.currency == currency.upper(),
            Event.at >= at - timedelta(minutes=MERGE_MINUTES),
            Event.at <= at + timedelta(minutes=MERGE_MINUTES),
            col.is_(None),
        )
    )
    norm, day = catalogue.normalise(title), uk_date(at)
    best: Event | None = None
    for ev in candidates:
        same_kind = (event_type_id is not None and ev.event_type_id == event_type_id) or (
            catalogue.normalise(ev.title) == norm
        )
        if not same_kind or uk_date(ev.at) != day:
            continue
        if best is None or abs(utc(ev.at) - at) < abs(utc(best.at) - at):
            best = ev
    return best


def upsert_ff(db: Session, items: list[dict], now: datetime) -> dict:
    """Items from `ff.parse_items`. Returns {seen, changed, keys, start, end}. Does not commit."""
    idx = catalogue.TypeIndex.load(db)
    counts: dict[str, int] = {}
    keys: set[str] = set()
    changed = 0
    for it in items:
        cur, title, at = it["currency"], it["title"], utc(it["at"])
        base = ff_key(cur, title, at)
        counts[base] = counts.get(base, 0) + 1
        key = ff_key(cur, title, at, counts[base])
        keys.add(key)
        et = catalogue.resolve(db, idx, cur, title)
        ev = db.scalar(select(Event).where(Event.ff_key == key))
        if ev is None:
            ev = find_partner(db, cur, et.id, title, at, missing="ff_key")
        dirty = False
        if ev is None:
            ev = Event(ff_key=key, sources=[FF], last_fetched_at=now, currency=cur, title=title, at=at)
            db.add(ev)
            dirty = True
        dirty |= _set(ev, "ff_key", key)
        dirty |= _add_source(ev, FF)
        for field, value in (
            ("title", title[:160]),
            ("currency", cur),
            ("event_type_id", et.id),
            ("all_day", it["all_day"]),
            ("impact", it["impact"]),
            ("forecast", it["forecast"]),
            ("previous", it["previous"]),
            ("forecast_value", parse_value(it["forecast"])),
            ("previous_value", parse_value(it["previous"])),
        ):
            dirty |= _set(ev, field, value)
        if utc(ev.at) != at:
            ev.at = at
            dirty = True
        dirty |= _restyle_actual(ev)
        if dirty:
            ev.last_fetched_at = now
            changed += 1
    db.flush()
    return {"seen": len(items), "changed": changed, "keys": keys}


def _restyle_actual(ev: Event) -> bool:
    """A JBlanked actual stored before Forex Factory's figures arrived ("254") takes FF's unit ("254K")."""
    fig = parse_figure(ev.actual)
    if fig is None or fig.unit or not (ev.forecast or ev.previous):
        return False
    text, value = style_like(fig.value, ev.forecast, ev.previous)
    if text is None or text == ev.actual:
        return False
    ev.actual, ev.actual_value = text, value
    return True


def prune_ff_week(db: Session, keys: set[str], start: date, end: date) -> int:
    """Forex Factory-only rows in the fetched week that the feed no longer lists (moved or cancelled).

    Rows with an actual, another source or stored price reactions are kept."""
    lo = datetime(start.year, start.month, start.day, tzinfo=UTC) - timedelta(days=1)
    hi = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=2)
    gone = 0
    for ev in db.scalars(select(Event).where(Event.at >= lo, Event.at < hi, Event.ff_key.is_not(None))):
        if ev.ff_key in keys or not (start <= uk_date(ev.at) <= end):
            continue
        if ev.sources != [FF] or ev.actual is not None:
            continue
        if db.scalar(select(PriceReaction.id).where(PriceReaction.event_id == ev.id).limit(1)):
            continue
        db.delete(ev)
        gone += 1
    db.flush()
    return gone


def _style_examples(db: Session, ev: Event) -> tuple[str | None, ...]:
    """Published figures to copy the unit and precision from: this row's, else the latest release of
    the same event type that has any (so a JBlanked-only NFP still reads "254K", not "254")."""
    own = (ev.forecast, ev.previous, ev.actual)
    if any(own) or not ev.event_type_id:
        return own
    sibling = db.scalar(
        select(Event)
        .where(Event.event_type_id == ev.event_type_id, Event.forecast.is_not(None), Event.id != (ev.id or 0))
        .order_by(Event.at.desc())
        .limit(1)
    )
    return (sibling.forecast, sibling.previous, sibling.actual) if sibling else own


def upsert_jb(db: Session, items: list[dict], now: datetime) -> dict:
    """Items from `jblanked.parse_items`. JBlanked fills the actual (and the forecast/previous when Forex
    Factory has none), sets `actual_at` the first time an actual appears. Does not commit."""
    idx = catalogue.TypeIndex.load(db)
    changed = 0
    for it in items:
        cur, title, at = it["currency"], it["title"], utc(it["at"])
        key = jb_key(it.get("event_id"), title, at)
        et = catalogue.resolve(db, idx, cur, title)
        ev = db.scalar(select(Event).where(Event.jb_key == key))
        if ev is None:
            ev = find_partner(db, cur, et.id, title, at, missing="jb_key")
        dirty = False
        if ev is None:
            ev = Event(
                title=title[:160],
                currency=cur,
                at=at,
                impact=it["impact"],
                event_type_id=et.id,
                sources=[JB],
                last_fetched_at=now,
            )
            db.add(ev)
            dirty = True
        dirty |= _set(ev, "jb_key", key)
        dirty |= _add_source(ev, JB)
        if it.get("event_id"):
            dirty |= _set(ev, "jb_event_id", it["event_id"])
            if et.jb_event_id is None:
                et.jb_event_id = it["event_id"]
        if FF not in ev.sources:
            # JBlanked is the only source for this row: it owns the schedule fields too.
            for field, value in (("title", title[:160]), ("impact", it["impact"]), ("event_type_id", et.id)):
                dirty |= _set(ev, field, value)
            if utc(ev.at) != at:
                ev.at = at
                dirty = True
        style = _style_examples(db, ev)
        if ev.forecast is None and it.get("forecast") is not None:
            text, value = style_like(it["forecast"], *style)
            dirty |= _set(ev, "forecast", text) | _set(ev, "forecast_value", value)
        if ev.previous is None and it.get("previous") is not None:
            text, value = style_like(it["previous"], *style)
            dirty |= _set(ev, "previous", text) | _set(ev, "previous_value", value)
        if it.get("actual") is not None:
            text, value = style_like(it["actual"], *_style_examples(db, ev))
            if value is not None and (ev.actual_value is None or abs(ev.actual_value - value) > 1e-9):
                dirty |= _set(ev, "actual", text) | _set(ev, "actual_value", value)
            if ev.actual is not None and ev.actual_at is None:
                ev.actual_at = now
                dirty = True
        if dirty:
            ev.last_fetched_at = now
            changed += 1
    db.flush()
    return {"seen": len(items), "changed": changed}


# ---- coverage ----------------------------------------------------------------------------------


def merge_ranges(ranges: list[tuple[date, date]]) -> list[tuple[date, date]]:
    """Overlapping or adjacent (next-day) ranges become one."""
    out: list[tuple[date, date]] = []
    for start, end in sorted(ranges):
        if out and start <= out[-1][1] + timedelta(days=1):
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def record_coverage(db: Session, source: str, start: date, end: date, note: str = "") -> None:
    """Add a range for `source` and merge it with that source's other ranges. Does not commit."""
    existing = list(db.scalars(select(NewsHistoryCoverage).where(NewsHistoryCoverage.source == source)))
    merged = merge_ranges([(r.start_date, r.end_date) for r in existing] + [(start, end)])
    if sorted((r.start_date, r.end_date) for r in existing) == merged:
        return
    db.execute(delete(NewsHistoryCoverage).where(NewsHistoryCoverage.source == source))
    db.add_all(
        NewsHistoryCoverage(source=source, start_date=a, end_date=b, note=note[:200]) for a, b in merged
    )
    db.flush()


def coverage_by_source(db: Session) -> list[dict]:
    rows = db.scalars(
        select(NewsHistoryCoverage).order_by(NewsHistoryCoverage.source, NewsHistoryCoverage.start_date)
    )
    return [{"source": r.source, "start_date": r.start_date, "end_date": r.end_date} for r in rows]


def coverage_ranges(db: Session) -> list[tuple[date, date]]:
    """Every source together, merged."""
    rows = db.execute(select(NewsHistoryCoverage.start_date, NewsHistoryCoverage.end_date)).all()
    return merge_ranges([(a, b) for a, b in rows])


def covered(ranges: list[tuple[date, date]], day: date) -> bool:
    return any(a <= day <= b for a, b in ranges)


def covered_days(ranges: list[tuple[date, date]], start: date, end: date) -> int:
    total = 0
    for a, b in ranges:
        lo, hi = max(a, start), min(b, end)
        if lo <= hi:
            total += (hi - lo).days + 1
    return total


# ---- feed runs -----------------------------------------------------------------------------------


def start_run(db: Session, feed: str, now: datetime, **detail) -> FeedRun:
    run = FeedRun(feed=feed, started_at=now, status="running", made_request=False, detail=detail or None)
    db.add(run)
    db.flush()
    return run


def finish_run(
    db: Session,
    run: FeedRun,
    now: datetime,
    *,
    status: str,
    error: str | None = None,
    http_status: int | None = None,
    seen: int = 0,
    changed: int = 0,
) -> None:
    run.finished_at = now
    run.status = status
    run.error = (error or None) and error[:1000]
    run.http_status = http_status
    run.events_seen = seen
    run.events_changed = changed
    db.commit()
