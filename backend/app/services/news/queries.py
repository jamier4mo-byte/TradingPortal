"""The read side of the News Room: EventOut and every view the API serves (docs/build/prompt4-api.md).

All functions take `now` (aware UTC) so tests freeze time. Dates in arguments are UK dates.
"""

import calendar as cal
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...models import Event, EventType, FeedRun, PriceReaction, Strategy, User
from .. import market_prefs
from ..journal_rules import UK_TZ, to_uk
from . import catalogue, jblanked, store
from .parse import surprise as surprise_of

IMPACT_LABEL = {"high": "High", "medium": "Med", "low": "Low", "holiday": "Holiday", "none": "None"}
FEEDS = ("forex_factory", "jblanked", "backfill")
SESSIONS = (
    ("Asia", time(0), time(8)),
    ("London", time(8), time(16, 30)),
    ("New York", time(13, 30), time(21)),
)
HORIZONS = (5, 15, 60)
HISTORY_LIMIT = 24
REACTION_RELEASES = 12
BRIEF_EVENT_LIMIT = 40
EMPTY_HISTORY = "No past releases stored yet. The history fills in as each release comes in."
EMPTY_REACTIONS = (
    "No price reactions stored yet. They're worked out after each release from Twelve Data prices."
)


def iso(dt: datetime | None) -> str | None:
    return None if dt is None else store.utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


def uk_day_bounds(start: date, end: date | None = None) -> tuple[datetime, datetime]:
    """UTC instants for UK midnight at `start` and UK midnight after `end` (inclusive range)."""
    end = end or start
    lo = datetime.combine(start, time(0), tzinfo=UK_TZ).astimezone(UTC)
    hi = datetime.combine(end + timedelta(days=1), time(0), tzinfo=UK_TZ).astimezone(UTC)
    return lo, hi


def uk_today(now: datetime) -> date:
    return to_uk(now).date()


# ---- EventOut ------------------------------------------------------------------------------------


@dataclass
class Ctx:
    imap: dict[str, list[str]]
    my_instruments: list[str]
    window_minutes: int
    types: dict[int, EventType] = field(default_factory=dict)

    @property
    def my_currencies(self) -> set[str]:
        mine = {i.upper() for i in self.my_instruments}
        return {cur for cur, insts in self.imap.items() if mine & set(insts)}

    def load_types(self, db: Session, events: list[Event]) -> None:
        ids = {e.event_type_id for e in events if e.event_type_id and e.event_type_id not in self.types}
        if ids:
            for et in db.scalars(select(EventType).where(EventType.id.in_(ids))):
                self.types[et.id] = et


def context(db: Session, user: User) -> Ctx:
    prefs = market_prefs.get_prefs(db, user)
    return Ctx(
        imap=market_prefs.instrument_map(db),
        my_instruments=list(prefs.instruments or []),
        window_minutes=prefs.news_window_minutes,
    )


def event_out(ev: Event, ctx: Ctx) -> dict:
    et = ctx.types.get(ev.event_type_id) if ev.event_type_id else None
    uk = to_uk(ev.at)
    instruments = ctx.imap.get(ev.currency.upper(), [])
    mine_set = {i.upper() for i in ctx.my_instruments}
    return {
        "id": ev.id,
        "title": ev.title,
        "name": et.name if et else ev.title,
        "currency": ev.currency,
        "at": iso(ev.at),
        "uk_date": uk.date().isoformat(),
        "uk_time": uk.strftime("%H:%M"),
        "all_day": ev.all_day,
        "impact": ev.impact,
        "impact_label": IMPACT_LABEL.get(ev.impact, ev.impact.title()),
        "forecast": ev.forecast,
        "previous": ev.previous,
        "actual": ev.actual,
        "revised": ev.revised,
        "released": ev.actual is not None,
        "surprise": surprise_of(
            ev.actual, ev.forecast, ev.actual_value, ev.forecast_value, et.higher_is_better if et else None
        ),
        "instruments": instruments,
        "mine": bool(mine_set & set(instruments)),
        "event_type_id": ev.event_type_id,
        "has_explanation": bool(et and et.explanation),
    }


def outs(db: Session, events: list[Event], ctx: Ctx) -> list[dict]:
    ctx.load_types(db, events)
    return [event_out(e, ctx) for e in events]


def _between(
    db: Session,
    lo: datetime,
    hi: datetime,
    *,
    currencies: set[str] | None = None,
    impacts: set[str] | None = None,
) -> list[Event]:
    stmt = select(Event).where(Event.at >= lo, Event.at < hi)
    if currencies is not None:
        stmt = stmt.where(func.upper(Event.currency).in_(sorted(currencies)))
    if impacts:
        stmt = stmt.where(Event.impact.in_(sorted(impacts)))
    return list(db.scalars(stmt.order_by(Event.at, Event.id)))


def last_updated_at(db: Session) -> datetime | None:
    return db.scalar(select(func.max(FeedRun.finished_at)).where(FeedRun.status == "ok"))


# ---- endpoints -----------------------------------------------------------------------------------


def status(db: Session, now: datetime) -> dict:
    feeds = []
    for feed in FEEDS:
        last = db.scalar(
            select(FeedRun).where(FeedRun.feed == feed).order_by(FeedRun.started_at.desc()).limit(1)
        )
        ok = db.scalar(
            select(func.max(FeedRun.finished_at)).where(FeedRun.feed == feed, FeedRun.status == "ok")
        )
        feeds.append(
            {
                "feed": feed,
                "last_success_at": iso(ok),
                "last_attempt_at": iso(last.started_at) if last else None,
                "last_status": last.status if last else None,
                "last_error": last.error if last and last.status == "error" else None,
            }
        )
    return {
        "last_updated_at": iso(last_updated_at(db)),
        "feeds": feeds,
        "coverage": [
            {
                "source": c["source"],
                "start_date": c["start_date"].isoformat(),
                "end_date": c["end_date"].isoformat(),
            }
            for c in store.coverage_by_source(db)
        ],
        "jblanked": {
            "configured": jblanked.configured(),
            "requests_today": jblanked.requests_today(db, now),
            "daily_budget": jblanked.daily_budget(),
            "next_slot_at": iso(jblanked.next_slot_at(db, now)),
        },
    }


def list_events(
    db: Session,
    user: User,
    now: datetime,
    *,
    start: date | None = None,
    end: date | None = None,
    currencies: list[str] | None = None,
    impacts: list[str] | None = None,
    mine: bool = False,
) -> dict:
    ctx = context(db, user)
    start = start or uk_today(now)
    end = end or start
    if end < start:
        start, end = end, start
    wanted: set[str] | None = {c.upper() for c in currencies} if currencies else None
    if mine:
        wanted = ctx.my_currencies if wanted is None else wanted & ctx.my_currencies
    lo, hi = uk_day_bounds(start, end)
    events = _between(db, lo, hi, currencies=wanted, impacts=set(impacts or []) or None)
    return {
        "events": outs(db, events, ctx),
        "from": start.isoformat(),
        "to": end.isoformat(),
        "last_updated_at": iso(last_updated_at(db)),
        "window_minutes": ctx.window_minutes,
        "my_instruments": ctx.my_instruments,
    }


def headline(events: list[dict], now: datetime) -> str:
    high = [e for e in events if e["impact"] == "high"]
    if not high:
        return "No high-impact news today."
    now_iso = iso(now) or ""
    lead = next((e for e in high if (e["at"] or "") >= now_iso), high[0])
    noun = "event" if len(high) == 1 else "events"
    return f"{len(high)} high-impact {noun} today – {lead['currency']} {lead['name']} at {lead['uk_time']}"


def today(db: Session, user: User, now: datetime) -> dict:
    ctx = context(db, user)
    lo, hi = uk_day_bounds(uk_today(now))
    events = outs(db, _between(db, lo, hi, currencies=ctx.my_currencies), ctx)
    return {
        "headline": headline(events, now),
        "high_count": sum(1 for e in events if e["impact"] == "high"),
        "events": events,
        "last_updated_at": iso(last_updated_at(db)),
    }


def next_event(db: Session, user: User, now: datetime, *, mine: bool = True) -> dict:
    ctx = context(db, user)
    stmt = select(Event).where(Event.impact == "high", Event.at > now)
    if mine:
        stmt = stmt.where(func.upper(Event.currency).in_(sorted(ctx.my_currencies)))
    ev = db.scalar(stmt.order_by(Event.at, Event.id).limit(1))
    return {
        "event": outs(db, [ev], ctx)[0] if ev else None,
        "seconds_until": int((store.utc(ev.at) - now).total_seconds()) if ev else None,
        "server_now": iso(now),
    }


def week_start(now: datetime) -> tuple[date, bool]:
    """Monday of this week; from Sunday 18:00 UK, next week's Monday (and the week-ahead is the default)."""
    uk = to_uk(now)
    monday = uk.date() - timedelta(days=uk.weekday())
    if uk.weekday() == 6 and uk.time() >= time(18):
        return monday + timedelta(days=7), True
    return monday, False


def week_ahead(
    db: Session, user: User, now: datetime, *, start: date | None = None, mine: bool = False
) -> dict:
    ctx = context(db, user)
    if start is None:
        monday, default_view = week_start(now)
    else:
        monday, default_view = start - timedelta(days=start.weekday()), False
    friday = monday + timedelta(days=4)
    lo, hi = uk_day_bounds(monday, friday)
    events = outs(
        db, _between(db, lo, hi, impacts={"high"}, currencies=ctx.my_currencies if mine else None), ctx
    )
    days = []
    for i in range(5):
        d = monday + timedelta(days=i)
        days.append(
            {
                "date": d.isoformat(),
                "label": f"{d:%a} {d.day} {d:%b}",
                "events": [e for e in events if e["uk_date"] == d.isoformat()],
            }
        )
    return {
        "start": monday.isoformat(),
        "end": friday.isoformat(),
        "default_view": default_view,
        "days": days,
    }


def timeline(db: Session, user: User, now: datetime, *, day: date | None = None, mine: bool = True) -> dict:
    ctx = context(db, user)
    day = day or uk_today(now)
    lo, hi = uk_day_bounds(day)
    events = outs(db, _between(db, lo, hi, currencies=ctx.my_currencies if mine else None), ctx)
    w = timedelta(minutes=ctx.window_minutes)
    windows = []
    for e in events:
        if e["impact"] == "high" and not e["all_day"]:
            at = datetime.fromisoformat(e["at"].replace("Z", "+00:00"))
            windows.append({"event_id": e["id"], "start": iso(at - w), "end": iso(at + w)})
    sessions = [
        {
            "name": name,
            "start": iso(datetime.combine(day, a, tzinfo=UK_TZ)),
            "end": iso(datetime.combine(day, b, tzinfo=UK_TZ)),
        }
        for name, a, b in SESSIONS
    ]
    return {
        "date": day.isoformat(),
        "window_minutes": ctx.window_minutes,
        "sessions": sessions,
        "events": events,
        "windows": windows,
    }


# ---- event detail --------------------------------------------------------------------------------


def _siblings(db: Session, ev: Event):
    if ev.event_type_id:
        return select(Event).where(Event.event_type_id == ev.event_type_id)
    return select(Event).where(Event.currency == ev.currency, Event.title == ev.title)


def _fmt_range(v: float) -> str:
    return f"{v:,.0f}" if abs(v) >= 10 else f"{v:.1f}".rstrip("0").rstrip(".")


def reactions_for(db: Session, events: list[Event], imap_order: list[str]) -> list[dict]:
    """Per instrument: releases, average range per horizon, and one row per release (newest first)."""
    if not events:
        return []
    ids = [e.id for e in events]
    by_event = {e.id: e for e in events}
    rows = db.scalars(select(PriceReaction).where(PriceReaction.event_id.in_(ids)))
    grouped: dict[str, dict[int, dict[int, PriceReaction]]] = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        grouped[r.instrument][r.event_id][r.horizon_minutes] = r
    order = {inst: i for i, inst in enumerate(imap_order)}
    out = []
    for inst in sorted(grouped, key=lambda i: (order.get(i, 99), i)):
        per_event = grouped[inst]
        unit = next(iter(next(iter(per_event.values())).values())).unit
        averages: dict[str, float | None] = {}
        for h in HORIZONS:
            vals = [
                hs[h].range_units
                for hs in per_event.values()
                if h in hs and hs[h].status == "ok" and hs[h].range_units is not None
            ]
            averages[str(h)] = round(mean(vals), 2) if vals else None
        release_rows = []
        for eid in sorted(per_event, key=lambda i: store.utc(by_event[i].at), reverse=True):
            hs = per_event[eid]
            release_rows.append(
                {
                    "event_id": eid,
                    "at": iso(by_event[eid].at),
                    "horizons": {
                        str(h): (
                            {
                                "status": hs[h].status,
                                "range": hs[h].range_units,
                                "move": hs[h].move_units,
                                "direction": hs[h].direction,
                            }
                            if h in hs
                            else {"status": "none", "range": None, "move": None, "direction": None}
                        )
                        for h in HORIZONS
                    },
                }
            )
        out.append(
            {
                "instrument": inst,
                "unit": unit,
                "releases": len(per_event),
                "average_range": averages,
                "rows": release_rows,
            }
        )
    return out


def summary_line(name: str, reactions: list[dict]) -> str | None:
    """E.g. "US CPI m/m: XAUUSD has averaged a 180-point range in the first 15 minutes over the last 12
    releases." Uses the instrument with the most 15-minute reactions."""
    best = None
    for r in reactions:
        n = sum(
            1
            for row in r["rows"]
            if row["horizons"]["15"]["status"] == "ok" and row["horizons"]["15"]["range"]
        )
        if r["average_range"]["15"] is not None and n and (best is None or n > best[1]):
            best = (r, n)
    if best is None:
        return None
    r, n = best
    word = "point" if r["unit"] == "points" else "pip"
    span = "the last release" if n == 1 else f"the last {n} releases"
    return (
        f"{name}: {r['instrument']} has averaged a {_fmt_range(r['average_range']['15'])}-{word} range "
        f"in the first 15 minutes over {span}."
    )


def detail(db: Session, user: User, event_id: int, now: datetime) -> dict | None:
    ev = db.get(Event, event_id)
    if ev is None:
        return None
    ctx = context(db, user)
    et = db.get(EventType, ev.event_type_id) if ev.event_type_id else None
    past = list(
        db.scalars(
            _siblings(db, ev)
            .where((Event.at <= now) | Event.actual.is_not(None))
            .order_by(Event.at.desc(), Event.id.desc())
            .limit(HISTORY_LIMIT)
        )
    )
    ctx.load_types(db, [ev, *past])
    hib = et.higher_is_better if et else None
    history = [
        {
            "event_id": p.id,
            "at": iso(p.at),
            "actual": p.actual,
            "forecast": p.forecast,
            "previous": p.previous,
            "surprise": surprise_of(p.actual, p.forecast, p.actual_value, p.forecast_value, hib),
        }
        for p in past
    ]
    reactions = reactions_for(db, past[:REACTION_RELEASES], ctx.imap.get(ev.currency.upper(), []))
    name = catalogue.display_name(et.name if et else ev.title, ev.currency)
    return {
        "event": event_out(ev, ctx),
        "type": (
            {
                "id": et.id,
                "name": et.name,
                "category": et.category,
                "explanation": et.explanation,
                "why_it_matters": et.why_it_matters,
                "higher_is_better": et.higher_is_better,
            }
            if et
            else None
        ),
        "history": history,
        "reactions": reactions,
        "summary": summary_line(name, reactions),
        "empty": {
            "history": None if history else EMPTY_HISTORY,
            "reactions": None if reactions else EMPTY_REACTIONS,
        },
    }


# ---- the Replay Journal brief --------------------------------------------------------------------


def brief_news(db: Session, user: User, strategy: Strategy, month: str | None) -> dict | None:
    """High-impact events for the strategy's next month to replay, for its instruments' currencies."""
    if not month:
        return None
    year, mon = (int(x) for x in month.split("-"))
    first = date(year, mon, 1)
    last = date(year, mon, cal.monthrange(year, mon)[1])
    ctx = context(db, user)
    instruments = [i.upper() for i in (strategy.instruments or [])]
    if instruments:
        currencies = {cur for cur, insts in ctx.imap.items() if set(instruments) & set(insts)}
    else:
        currencies = set(ctx.imap)
    lo, hi = uk_day_bounds(first, last)
    events = _between(db, lo, hi, currencies=currencies, impacts={"high"})
    days = (last - first).days + 1
    have = store.covered_days(store.coverage_ranges(db), first, last)
    label = f"{first:%B %Y}"
    if have >= days:
        status = "ok"
        note = f"{len(events)} high-impact {'event' if len(events) == 1 else 'events'} in {label}."
    elif have:
        status = "partial"
        note = f"News history covers {have} of {days} days in {label}, so some events may be missing."
    else:
        status = "no_data"
        note = f"No news history for {label} yet, so news windows can't be checked for this month."
    return {
        "month": month,
        "status": status,
        "high_count": len(events),
        "events": outs(db, events[:BRIEF_EVENT_LIMIT], ctx),
        "note": note,
    }
