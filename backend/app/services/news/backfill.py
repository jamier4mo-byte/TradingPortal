"""`make news-backfill`: load JBlanked history month by month, resumably, inside the API's limits.

Each month is one `{src}/calendar/range/` request (paid credits on JBlanked's current pricing). Between
requests it waits for the global 5-minute slot, it never exceeds the daily request budget shared with the
scheduler, and it stops cleanly when the key is missing or invalid or the API refuses (no credits, rate
limit). The cursor lives in app_state["news_backfill"], so running it again carries on where it stopped.
"""

import time as _time
from collections.abc import Callable
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from ...models import AppState, utcnow
from ..journal_rules import to_uk
from . import jblanked, store, tagging

STATE_KEY = "news_backfill"
DEFAULT_START = date(2023, 1, 1)
COUNTDOWN_STEP = 10  # seconds between countdown lines


def month_ranges(start: date, end: date) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    a = start
    while a <= end:
        nxt = date(a.year + (a.month == 12), a.month % 12 + 1, 1)
        out.append((a, min(nxt - timedelta(days=1), end)))
        a = nxt
    return out


def _state(db: Session) -> AppState | None:
    return db.get(AppState, STATE_KEY)


def _save(db: Session, value: dict) -> None:
    row = _state(db)
    if row is None:
        db.add(AppState(key=STATE_KEY, value=value))
    else:
        row.value = value
    db.commit()


def _wait_for_slot(
    db: Session, now_fn: Callable[[], datetime], sleep: Callable[[float], None], echo: Callable[..., None]
) -> None:
    while True:
        nxt = jblanked.next_slot_at(db, now_fn())
        if nxt is None:
            return
        left = (nxt - now_fn()).total_seconds()
        if left <= 0:
            return
        m, s = divmod(int(left + 0.999), 60)
        echo(f"  waiting {m}:{s:02d} for the JBlanked slot (one request every 5 minutes)…")
        sleep(min(left, COUNTDOWN_STEP))


def run(
    db: Session,
    *,
    start: date | None = None,
    max_requests: int | None = None,
    now_fn: Callable[[], datetime] = utcnow,
    sleep: Callable[[float], None] = _time.sleep,
    echo: Callable[..., None] = print,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    problem = jblanked.key_problem()
    if problem:
        echo(problem)
        return {"status": "not_configured", "requests": 0}
    first = start or DEFAULT_START
    saved = (_state(db).value if _state(db) else None) or {}
    cursor = first
    if saved.get("start") == first.isoformat() and saved.get("next"):
        cursor = max(first, date.fromisoformat(saved["next"]))
    yesterday = to_uk(now_fn()).date() - timedelta(days=1)
    months = month_ranges(cursor, yesterday)
    limit = max_requests if max_requests is not None else jblanked.daily_budget()
    if not months:
        echo(f"Nothing to load: history is already loaded from {first} to {yesterday}.")
    made, status, loaded = 0, "done", 0
    i = 0
    while i < len(months):
        a, b = months[i]
        if made >= limit:
            echo(
                f"Stopped after {made} request(s) (--max-requests {limit}). Run it again to carry on "
                f"from {a}."
            )
            status = "paused"
            break
        if jblanked.requests_today(db, now_fn()) >= jblanked.daily_budget():
            echo(
                f"The JBlanked daily budget ({jblanked.daily_budget()} a day, shared with the News Room) "
                f"is used up. Run it again tomorrow to carry on from {a}."
            )
            status = "budget_used"
            break
        _wait_for_slot(db, now_fn, sleep, echo)
        res = jblanked.try_fetch(
            db, now_fn(), kind="range", start=a, end=b, feed="backfill", transport=transport
        )
        if res["status"] == "slot_busy":
            continue  # another process took the slot first: wait again
        if res["status"] in ("not_configured", "budget_used"):
            echo(res["error"])
            status = res["status"]
            break
        made += 1
        if res["status"] == "ok":
            loaded += res.get("seen", 0)
            _save(db, {"start": first.isoformat(), "next": (b + timedelta(days=1)).isoformat()})
            echo(f"Loaded {a:%b %Y}: {res.get('seen', 0)} events ({res.get('changed', 0)} new or changed).")
            i += 1
            continue
        if res["status"] == "refused":
            code = res.get("http_status")
            why = (
                "the key was refused (check JBLANKED_API_KEY)"
                if code in (401, 403)
                else "JBlanked refused the request (credits or rate limit)"
            )
            echo(f"Stopped: {why}. {res['error']}")
            status = "refused"
        else:
            echo(f"Stopped: the request for {a:%b %Y} failed. {res.get('error')}")
            status = "error"
        break
    if made:
        tagging.retag(db)
    ranges = [c for c in store.coverage_by_source(db) if c["source"] == "jblanked"]
    if ranges:
        spans = ", ".join(f"{c['start_date']} to {c['end_date']}" for c in ranges)
        echo(f"JBlanked history coverage: {spans}")
    else:
        echo("No JBlanked history coverage yet.")
    return {"status": status, "requests": made, "events": loaded}
