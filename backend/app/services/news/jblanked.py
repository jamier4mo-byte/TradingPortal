"""JBlanked News API: released actuals and history (base https://www.jblanked.com/news/api/).

Endpoints (trailing slash): `{src}/calendar/today/`, `{src}/calendar/week/`,
`{src}/calendar/range/?from=YYYY-MM-DD&to=YYYY-MM-DD`, `{src}/{EVENT_ID}/history/`, where `{src}` is
`settings.jblanked_source`. Header `Authorization: Api-Key <key>`; a key under 30 characters is treated
as not configured. The key is never logged or stored anywhere but the settings.

Pricing (6 Nov 2026): free use is one request a day, and only on `/calendar/today/`; week, range and
history spend paid credits. Two limits, both global across processes:
  (a) one request per `jblanked_min_interval_minutes` (a DB slot via `leases.claim_slot`);
  (b) `jblanked_daily_requests` per UTC day, counted from `feed_runs` (jblanked + backfill).
Schedule: once per UK day after 21:15 (after the US releases) on `/calendar/today/`; with a budget above
one, also within 20 minutes after a high-impact event that still lacks an actual.
"""

import logging
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.settings import get_settings
from ...models import Event, FeedRun
from .. import http, leases
from ..journal_rules import UK_TZ, to_uk
from . import store

log = logging.getLogger("trading_portal.news.jblanked")

BASE_URL = "https://www.jblanked.com/news/api/"
FEED = "jblanked"
BUDGET_FEEDS = ("jblanked", "backfill")
SLOT = "jblanked"
MIN_KEY_LENGTH = 30
# JBlanked's "Date" has no zone. It is the MT5 server time: GMT+2 in winter and GMT+3 in summer,
# following EU DST, which is exactly Europe/Athens. Inferred from MQL5 calendar conventions, not
# documented by JBlanked: confirm when a live response is recorded.
SERVER_TZ = ZoneInfo("Europe/Athens")
DATE_FORMATS = ("%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M")
IMPACT = {"high": "high", "medium": "medium", "low": "low", "none": "none", "holiday": "holiday"}
EVENING = time(21, 15)  # UK: after the US releases
AFTER_EVENT = timedelta(minutes=20)
REFUSED = {401, 402, 403, 429}


def key_problem(key: str | None = None) -> str | None:
    """None when the key looks usable; otherwise a message for people (never the key itself)."""
    key = key if key is not None else get_settings().jblanked_api_key
    if not key:
        return "JBlanked isn't configured: set JBLANKED_API_KEY."
    if len(key.strip()) < MIN_KEY_LENGTH:
        return (
            "The JBlanked key looks too short to be valid (keys are 30+ characters). Check JBLANKED_API_KEY."
        )
    return None


def configured() -> bool:
    return key_problem() is None


def parse_date(text: str) -> datetime:
    """ "2024.02.08 15:30:00" in the MT5 server zone → aware UTC."""
    text = text.strip()
    for fmt in DATE_FORMATS:
        try:
            naive = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return naive.replace(tzinfo=SERVER_TZ).astimezone(UTC)
    raise ValueError(f"Unreadable JBlanked date: {text!r}")


def _num(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_items(data) -> list[dict]:
    if isinstance(data, dict):  # some responses wrap the list
        data = data.get("results") or data.get("data") or data.get("events")
    if not isinstance(data, list):
        raise ValueError("JBlanked response changed shape: expected a JSON array of events")
    out: list[dict] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        title = str(row.get("Name") or "").strip()
        currency = str(row.get("Currency") or "").strip().upper()
        try:
            at = parse_date(str(row.get("Date") or ""))
        except ValueError:
            continue
        if not (title and currency):
            continue
        try:
            event_id = int(row.get("Event_ID") or 0) or None
        except (TypeError, ValueError):
            event_id = None
        out.append(
            {
                "title": title,
                "currency": currency,
                "at": at,
                "impact": IMPACT.get(str(row.get("Impact") or "").strip().lower(), "none"),
                "event_id": event_id,
                "actual": _num(row.get("Actual")),
                "forecast": _num(row.get("Forecast")),
                "previous": _num(row.get("Previous")),
            }
        )
    return out


def _error_text(res: httpx.Response) -> str:
    try:
        body = res.json()
    except ValueError:
        body = None
    detail = None
    if isinstance(body, dict):
        detail = body.get("detail") or body.get("message") or body.get("error")
    if not detail:
        detail = (res.text or "").strip()[:200] or res.reason_phrase
    return f"HTTP {res.status_code}: {detail}"


# ---- limits --------------------------------------------------------------------------------------


def _utc_midnight(now: datetime) -> datetime:
    return datetime.combine(store.utc(now).date(), time(0), tzinfo=UTC)


def requests_today(db: Session, now: datetime) -> int:
    return (
        db.scalar(
            select(func.count(FeedRun.id)).where(
                FeedRun.feed.in_(BUDGET_FEEDS),
                FeedRun.made_request.is_(True),
                FeedRun.started_at >= _utc_midnight(now),
            )
        )
        or 0
    )


def daily_budget() -> int:
    return max(0, get_settings().jblanked_daily_requests)


def interval() -> timedelta:
    return timedelta(minutes=max(1, get_settings().jblanked_min_interval_minutes))


def next_slot_at(db: Session, now: datetime) -> datetime | None:
    at = leases.next_slot_at(db, SLOT)
    return at if at and store.utc(at) > now else None


def reason_due(db: Session, now: datetime) -> str | None:
    """Why the scheduler should call JBlanked now, or None. Cheap: two small queries at most."""
    if not configured():
        return None
    used, budget = requests_today(db, now), daily_budget()
    if used >= budget:
        return None
    uk = to_uk(now)
    evening_from = datetime.combine(uk.date(), EVENING, tzinfo=UK_TZ).astimezone(UTC)
    if now >= evening_from:
        done = db.scalar(
            select(FeedRun.id)
            .where(FeedRun.feed == FEED, FeedRun.made_request.is_(True), FeedRun.started_at >= evening_from)
            .limit(1)
        )
        return None if done else "evening"
    if budget - used <= 1:
        return None  # keep the last request of the day for the evening call
    waiting = db.scalar(
        select(Event.at)
        .where(
            Event.impact == "high",
            Event.actual.is_(None),
            Event.at <= now,
            Event.at >= now - AFTER_EVENT,
        )
        .order_by(Event.at.desc())
        .limit(1)
    )
    if waiting is None:
        return None
    asked = db.scalar(
        select(FeedRun.id)
        .where(FeedRun.feed == FEED, FeedRun.made_request.is_(True), FeedRun.started_at >= waiting)
        .limit(1)
    )
    return None if asked else "after_release"


# ---- requests ------------------------------------------------------------------------------------


def _path(kind: str, start: date | None, end: date | None) -> tuple[str, dict]:
    src = get_settings().jblanked_source
    if kind == "today":
        return f"{src}/calendar/today/", {}
    if kind == "week":
        return f"{src}/calendar/week/", {}
    if kind == "range" and start and end:
        return f"{src}/calendar/range/", {"from": start.isoformat(), "to": end.isoformat()}
    raise ValueError(f"Unknown JBlanked request {kind!r}")


def try_fetch(
    db: Session,
    now: datetime,
    *,
    kind: str = "today",
    start: date | None = None,
    end: date | None = None,
    feed: str = FEED,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    """Enforces the key check, the daily budget and the global slot, then makes one request."""
    problem = key_problem()
    if problem:
        return {"status": "not_configured", "error": problem}
    if requests_today(db, now) >= daily_budget():
        return {"status": "budget_used", "error": "JBlanked daily request budget used."}
    if not leases.claim_slot(db, SLOT, interval(), now=now):
        return {"status": "slot_busy", "next_slot_at": next_slot_at(db, now)}
    return _request(db, now, kind=kind, start=start, end=end, feed=feed, transport=transport)


def _request(
    db: Session,
    now: datetime,
    *,
    kind: str,
    start: date | None,
    end: date | None,
    feed: str,
    transport: httpx.BaseTransport | None,
) -> dict:
    path, params = _path(kind, start, end)
    span = {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None}
    run = store.start_run(db, feed, now, kind=kind, **span)
    run.made_request = True
    db.commit()
    key = (get_settings().jblanked_api_key or "").strip()
    try:
        with http.client(transport, base_url=BASE_URL, headers={"Authorization": f"Api-Key {key}"}) as c:
            res = c.get(path, params=params)
    except (httpx.HTTPError, http.NetworkBlocked) as exc:
        store.finish_run(db, run, now, status="error", error=f"Request failed: {type(exc).__name__}")
        return {"status": "error", "error": run.error}
    if not 200 <= res.status_code < 300:
        msg = _error_text(res)
        store.finish_run(db, run, now, status="error", error=msg, http_status=res.status_code)
        return {
            "status": "refused" if res.status_code in REFUSED else "error",
            "error": msg,
            "http_status": res.status_code,
        }
    try:
        items = parse_items(res.json())
    except ValueError as exc:
        store.finish_run(db, run, now, status="error", error=str(exc), http_status=res.status_code)
        return {"status": "error", "error": str(exc), "http_status": res.status_code}
    try:
        result = store.upsert_jb(db, items, now)
        if kind == "today":
            day = now.astimezone(SERVER_TZ).date()
            store.record_coverage(db, "jblanked", day, day, note="JBlanked calendar")
        elif kind == "range" and start and end:
            store.record_coverage(db, "jblanked", start, end, note="JBlanked calendar range")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        log.exception("JBlanked upsert failed")
        run = db.get(FeedRun, run.id)
        store.finish_run(db, run, now, status="error", error=f"Upsert failed: {type(exc).__name__}: {exc}")
        return {"status": "error", "error": run.error}
    store.finish_run(
        db, run, now, status="ok", http_status=res.status_code, seen=result["seen"], changed=result["changed"]
    )
    return {"status": "ok", "seen": result["seen"], "changed": result["changed"]}


def refresh_if_due(db: Session, now: datetime, transport: httpx.BaseTransport | None = None) -> dict:
    reason = reason_due(db, now)
    if reason is None:
        return {"status": "not_due"}
    out = try_fetch(db, now, kind="today", transport=transport)
    out["reason"] = reason
    return out
