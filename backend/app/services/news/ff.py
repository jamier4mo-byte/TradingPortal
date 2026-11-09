"""Forex Factory weekly JSON (`settings.ff_calendar_url`, plus `ff_calendar_next_url` for next week): the
schedule, impact, forecast and previous.

The feed is an array of {"title","country","date","impact","forecast","previous"}; `country` is the
currency code, `date` is ISO with a US Eastern offset ("2026-11-06T08:30:00-05:00", "-04:00" in US summer
time), so converting with the offset gives exact UTC across both DST changes. No ids and no actuals.
Fetched server-side at most every `ff_min_interval_minutes` (hourly), with our generic User-Agent.
Never scrape forexfactory.com itself.
"""

import logging
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.settings import get_settings
from ...models import FeedRun
from .. import http
from . import store

log = logging.getLogger("trading_portal.news.ff")

FEED = "forex_factory"
FEED_NEXT = "forex_factory_next"  # next week's file: its own runs, so its schedule and errors stay separate
RETRY_AFTER_ERROR = timedelta(minutes=15)
IMPACT = {"high": "high", "medium": "medium", "low": "low", "holiday": "holiday", "non-economic": "none"}


def parse_items(data) -> list[dict]:
    """The feed's rows, normalised. Rows without a currency, title or readable date are skipped."""
    if not isinstance(data, list):
        raise ValueError("Forex Factory feed changed shape: expected a JSON array")
    out: list[dict] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        currency = str(row.get("country") or "").strip().upper()
        raw_date = str(row.get("date") or "").strip()
        if not (title and currency and raw_date):
            continue
        try:
            at = datetime.fromisoformat(raw_date)
        except ValueError:
            continue
        if at.tzinfo is None:
            continue  # the feed always carries an offset; without one the time is a guess
        impact = IMPACT.get(str(row.get("impact") or "").strip().lower(), "low")
        out.append(
            {
                "title": title,
                "currency": currency,
                "at": store.utc(at),
                "impact": impact,
                "all_day": impact == "holiday",
                "forecast": (str(row.get("forecast") or "").strip() or None),
                "previous": (str(row.get("previous") or "").strip() or None),
                "eastern_date": at.date(),
            }
        )
    return out


def week_of(items: list[dict]) -> tuple[date, date] | None:
    """The feed's Sunday–Saturday week (its dates are US Eastern; the first row fixes the week)."""
    if not items:
        return None
    first = min(it["eastern_date"] for it in items)
    sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    return sunday, sunday + timedelta(days=6)


def due(db: Session, now: datetime, feed: str = FEED) -> bool:
    """At most once per interval after a success, and every 15 minutes after a failure."""
    last = db.execute(
        select(FeedRun.started_at, FeedRun.status)
        .where(FeedRun.feed == feed, FeedRun.made_request.is_(True))
        .order_by(FeedRun.started_at.desc())
        .limit(1)
    ).first()
    if last is None:
        return True
    wait = timedelta(minutes=get_settings().ff_min_interval_minutes)
    if last.status == "error":
        wait = min(wait, RETRY_AFTER_ERROR)
    return now - store.utc(last.started_at) >= wait


def fetch(
    db: Session,
    now: datetime,
    transport: httpx.BaseTransport | None = None,
    *,
    feed: str = FEED,
    url: str | None = None,
) -> dict:
    """One request, upsert, coverage for the week. Every attempt leaves a `feed_runs` row."""
    url = url or get_settings().ff_calendar_url
    run = store.start_run(db, feed, now)
    run.made_request = True
    db.commit()
    try:
        with http.client(transport) as c:
            res = c.get(url)
    except (httpx.HTTPError, http.NetworkBlocked) as exc:
        store.finish_run(db, run, now, status="error", error=f"Request failed: {type(exc).__name__}: {exc}")
        return {"status": "error", "error": run.error}
    if res.status_code == 404 and feed == FEED_NEXT:
        # Next week's file isn't there yet (or the publisher dropped it): not a failure of the calendar.
        msg = "Next week's schedule isn't published yet"
        store.finish_run(db, run, now, status="skipped", error=msg, http_status=404)
        return {"status": "skipped", "error": msg, "http_status": 404}
    if res.status_code != 200:
        msg = f"HTTP {res.status_code} from Forex Factory feed"
        store.finish_run(db, run, now, status="error", error=msg, http_status=res.status_code)
        return {"status": "error", "error": msg, "http_status": res.status_code}
    try:
        items = parse_items(res.json())
    except ValueError as exc:
        store.finish_run(db, run, now, status="error", error=str(exc), http_status=res.status_code)
        return {"status": "error", "error": str(exc)}
    try:
        result = store.upsert_ff(db, items, now)
        week = week_of(items)
        if week:
            store.prune_ff_week(db, result["keys"], *week)
            store.record_coverage(db, FEED, *week, note="Forex Factory weekly feed")
    except Exception as exc:  # noqa: BLE001 — log the failure on the run, keep the other feed going
        db.rollback()
        log.exception("Forex Factory upsert failed")
        run = db.get(FeedRun, run.id)
        store.finish_run(db, run, now, status="error", error=f"Upsert failed: {type(exc).__name__}: {exc}")
        return {"status": "error", "error": run.error}
    store.finish_run(
        db, run, now, status="ok", http_status=200, seen=result["seen"], changed=result["changed"]
    )
    return {"status": "ok", "seen": result["seen"], "changed": result["changed"]}


def refresh_if_due(db: Session, now: datetime, transport: httpx.BaseTransport | None = None) -> dict:
    """This week's file, then (when configured) next week's, each on its own interval. The result is this
    week's, with next week's under "next" whenever that one made a request."""
    out = fetch(db, now, transport) if due(db, now) else {"status": "not_due"}
    next_url = get_settings().ff_calendar_next_url
    if next_url and due(db, now, FEED_NEXT):
        try:
            out["next"] = fetch(db, now, transport, feed=FEED_NEXT, url=next_url)
        except Exception as exc:  # noqa: BLE001 — next week failing never undoes this week
            db.rollback()
            log.exception("Forex Factory next-week fetch failed")
            out["next"] = {"status": "error", "error": type(exc).__name__}
    return out
