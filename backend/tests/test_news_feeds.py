"""Both feeds against recorded fixtures: upserts, the merge, the JBlanked limits, failures, backfill.

No test touches the network: every request goes to an httpx.MockTransport serving fixture JSON.
"""

import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.core.settings import get_settings
from app.models import AppState, Event, EventType, FeedRun, NewsHistoryCoverage
from app.services.news import backfill, ff, jblanked, jobs, store
from tests.conftest import FIXTURES

NEWS = FIXTURES / "news"
FF_WEEK = "ff_week_2026-11-01.json"
KEY = "test-jblanked-key-0123456789-abcdefghij"
# Friday 6 Nov 2026 (UK = UTC in winter)
FRI_MORNING = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
FRI_EVENING = datetime(2026, 11, 6, 21, 30, tzinfo=UTC)


def fixture(name: str):
    return json.loads((NEWS / name).read_text())


class Recorder:
    """A MockTransport handler that serves fixtures by path and records every request."""

    def __init__(self, routes: dict[str, tuple[int, object]] | None = None, default=(200, [])):
        self.routes = routes or {}
        self.default = default
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        for fragment, (status, body) in self.routes.items():
            if fragment in str(request.url):
                return httpx.Response(status, json=body)
        status, body = self.default
        return httpx.Response(status, json=body)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


def ff_transport(name: str = FF_WEEK, status: int = 200) -> Recorder:
    return Recorder(default=(status, fixture(name) if status == 200 else {"error": "oops"}))


def jb_transport(body=None, status: int = 200) -> Recorder:
    return Recorder(default=(status, body if body is not None else fixture("jb_today_2026-11-06.json")))


@pytest.fixture
def jb_key(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "jblanked_api_key", KEY)
    monkeypatch.setattr(s, "jblanked_daily_requests", 1)
    return s


def load_ff(db, now=FRI_MORNING, name=FF_WEEK) -> dict:
    return ff.fetch(db, now, ff_transport(name).transport)


def event(db, currency: str, title: str) -> Event:
    return db.scalar(select(Event).where(Event.currency == currency, Event.title == title))


def snapshot(db) -> list[tuple]:
    rows = db.scalars(select(Event).order_by(Event.id))
    return [
        (e.id, e.title, e.at, e.impact, e.forecast, e.previous, e.actual, e.updated_at, tuple(e.sources))
        for e in rows
    ]


# ---- Forex Factory --------------------------------------------------------------------------------


def test_ff_fetch_upserts_and_records_the_week(db):
    out = load_ff(db)
    assert out == {"status": "ok", "seen": 19, "changed": 19}
    nfp = event(db, "USD", "Non-Farm Employment Change")
    assert nfp.at == datetime(2026, 11, 6, 13, 30, tzinfo=UTC)
    assert (nfp.forecast, nfp.forecast_value, nfp.previous_value) == ("110K", 110000.0, 22000.0)
    assert nfp.event_type.key == "USD:nfp" and nfp.sources == ["forex_factory"] and nfp.actual is None
    # Unknown titles get an unseeded type with no explanation.
    waller = event(db, "USD", "FOMC Member Waller Speaks")
    assert waller.event_type.seeded is False and waller.event_type.explanation is None
    assert waller.event_type.key == "USD:fomc_member_waller_speaks"
    cov = list(db.scalars(select(NewsHistoryCoverage)))
    assert [(c.source, c.start_date, c.end_date) for c in cov] == [
        ("forex_factory", date(2026, 11, 1), date(2026, 11, 7))
    ]
    run = db.scalar(select(FeedRun))
    assert (run.feed, run.status, run.made_request, run.events_seen) == ("forex_factory", "ok", True, 19)
    assert run.finished_at is not None


def test_ff_fetching_the_same_feed_twice_changes_nothing(db):
    load_ff(db)
    before = snapshot(db)
    types = db.scalar(select(func.count(EventType.id)))
    out = load_ff(db, FRI_MORNING + timedelta(hours=1))
    assert out["changed"] == 0
    assert snapshot(db) == before
    assert db.scalar(select(func.count(EventType.id))) == types


def test_ff_a_changed_forecast_or_time_updates_the_row(db):
    load_ff(db)
    nfp_id = event(db, "USD", "Non-Farm Employment Change").id
    data = fixture(FF_WEEK)
    for row in data:
        if row["title"] == "Non-Farm Employment Change":
            row["forecast"] = "125K"
        if row["title"] == "Fed Chair Powell Speaks":
            row["date"] = "2026-11-06T14:30:00-05:00"  # moved later the same day
    out = ff.fetch(db, FRI_MORNING + timedelta(hours=1), Recorder(default=(200, data)).transport)
    assert out["changed"] == 2
    db.expire_all()
    nfp = db.get(Event, nfp_id)
    assert (nfp.forecast, nfp.forecast_value) == ("125K", 125000.0)
    powell = event(db, "USD", "Fed Chair Powell Speaks")
    assert powell.at == datetime(2026, 11, 6, 19, 30, tzinfo=UTC)
    assert db.scalar(select(func.count(Event.id)).where(Event.title == "Fed Chair Powell Speaks")) == 1


def test_ff_drops_rows_the_feed_no_longer_lists(db):
    load_ff(db)
    data = [r for r in fixture(FF_WEEK) if r["title"] != "Crude Oil Inventories"]
    ff.fetch(db, FRI_MORNING + timedelta(hours=1), Recorder(default=(200, data)).transport)
    assert event(db, "USD", "Crude Oil Inventories") is None
    assert event(db, "USD", "ISM Services PMI") is not None


def test_ff_runs_at_most_hourly_and_retries_sooner_after_an_error(db):
    assert ff.due(db, FRI_MORNING)
    load_ff(db)
    assert not ff.due(db, FRI_MORNING + timedelta(minutes=59))
    assert ff.due(db, FRI_MORNING + timedelta(minutes=60))
    ff.fetch(db, FRI_MORNING + timedelta(hours=2), ff_transport(status=500).transport)
    assert not ff.due(db, FRI_MORNING + timedelta(hours=2, minutes=14))
    assert ff.due(db, FRI_MORNING + timedelta(hours=2, minutes=15))


# ---- JBlanked -------------------------------------------------------------------------------------


def test_jblanked_merges_into_the_forex_factory_row_with_the_actual(db, jb_key):
    load_ff(db)
    rows_before = db.scalar(select(func.count(Event.id)))
    rec = jb_transport()
    out = jblanked.try_fetch(db, FRI_EVENING, transport=rec.transport)
    assert out["status"] == "ok" and out["seen"] == 6
    req = rec.requests[0]
    assert str(req.url) == "https://www.jblanked.com/news/api/forex-factory/calendar/today/"
    assert req.headers["Authorization"] == f"Api-Key {KEY}"
    nfp = event(db, "USD", "Non-Farm Employment Change")
    assert (nfp.actual, nfp.actual_value, nfp.forecast) == ("254K", 254000.0, "110K")
    assert nfp.actual_at == FRI_EVENING and nfp.jb_event_id == 840030016
    assert nfp.sources == ["forex_factory", "jblanked"]
    assert nfp.jb_key == "840030016:2026-11-06T13:30Z"
    assert event(db, "USD", "Unemployment Rate").actual == "4.2%"
    assert event(db, "CAD", "Employment Change").actual == "-8.4K"
    uom = event(db, "USD", "Prelim UoM Consumer Sentiment")
    assert uom.actual == "51.9" and uom.jb_key == "prelim_uom_consumer_sentiment:2026-11-06T15:00Z"
    # Consumer Credit isn't in the FF week: a JBlanked-only row (one new row in all).
    credit = event(db, "USD", "Consumer Credit m/m")
    assert credit.sources == ["jblanked"] and credit.impact == "low" and credit.forecast == "10.5"
    assert db.scalar(select(func.count(Event.id))) == rows_before + 1
    # actual_at is set the first time only; a second identical fetch changes nothing.
    again = jblanked._request(
        db, FRI_EVENING + timedelta(minutes=10), kind="today", start=None, end=None, feed="jblanked",
        transport=jb_transport().transport,
    )  # fmt: skip
    assert again["changed"] == 0
    assert event(db, "USD", "Non-Farm Employment Change").actual_at == FRI_EVENING
    cov = {c.source for c in db.scalars(select(NewsHistoryCoverage))}
    assert cov == {"forex_factory", "jblanked"}


def test_forex_factory_after_jblanked_merges_too(db, jb_key):
    jblanked.try_fetch(db, FRI_EVENING, transport=jb_transport().transport)
    load_ff(db, FRI_EVENING + timedelta(minutes=1))
    rows = list(db.scalars(select(Event).where(Event.title == "Non-Farm Employment Change")))
    assert len(rows) == 1
    assert rows[0].sources == ["jblanked", "forex_factory"] and rows[0].ff_key and rows[0].jb_key
    assert (rows[0].actual, rows[0].actual_value) == ("254K", 254000.0)  # takes FF's unit once it arrives


def test_jblanked_slot_allows_one_request_per_five_minutes(db, jb_key, monkeypatch):
    monkeypatch.setattr(get_settings(), "jblanked_daily_requests", 10)
    rec = jb_transport()
    assert jblanked.try_fetch(db, FRI_EVENING, transport=rec.transport)["status"] == "ok"
    busy = jblanked.try_fetch(db, FRI_EVENING + timedelta(minutes=1), transport=rec.transport)
    assert busy["status"] == "slot_busy" and busy["next_slot_at"] == FRI_EVENING + timedelta(minutes=5)
    assert (
        jblanked.try_fetch(db, FRI_EVENING + timedelta(minutes=4, seconds=59), transport=rec.transport)[
            "status"
        ]
        == "slot_busy"
    )
    assert (
        jblanked.try_fetch(db, FRI_EVENING + timedelta(minutes=5), transport=rec.transport)["status"] == "ok"
    )
    assert len(rec.requests) == 2


def test_two_refresh_calls_a_minute_apart_make_one_jblanked_request(db, jb_key, monkeypatch):
    monkeypatch.setattr(get_settings(), "jblanked_daily_requests", 10)
    ffr, jbr = ff_transport(), jb_transport()
    first = jobs.refresh_feeds(
        db, FRI_EVENING, live=True, ff_transport=ffr.transport, jb_transport=jbr.transport
    )
    second = jobs.refresh_feeds(
        db,
        FRI_EVENING + timedelta(minutes=1),
        live=True,
        ff_transport=ffr.transport,
        jb_transport=jbr.transport,
    )
    assert first["jblanked"]["status"] == "ok" and first["jblanked"]["reason"] == "evening"
    assert first["forex_factory"]["status"] == "ok"
    assert second == {"forex_factory": {"status": "not_due"}, "jblanked": {"status": "not_due"}}
    assert len(jbr.requests) == 1 and len(ffr.requests) == 1


def test_daily_budget_counts_requests_per_utc_day(db, jb_key):
    rec = jb_transport()
    assert jblanked.try_fetch(db, FRI_EVENING, transport=rec.transport)["status"] == "ok"
    later = jblanked.try_fetch(db, FRI_EVENING + timedelta(minutes=10), transport=rec.transport)
    assert later["status"] == "budget_used"
    assert jblanked.requests_today(db, FRI_EVENING) == 1
    assert jblanked.reason_due(db, FRI_EVENING + timedelta(minutes=30)) is None
    # A new UTC day has a fresh budget; the evening call is due again after 21:15 UK.
    next_day = FRI_EVENING + timedelta(days=1)
    assert jblanked.requests_today(db, next_day) == 0
    assert jblanked.reason_due(db, next_day) == "evening"
    assert jblanked.reason_due(db, next_day - timedelta(hours=1)) is None  # 20:30 UK: not yet
    assert len(rec.requests) == 1


def test_errors_are_budgeted_too(db, jb_key):
    rec = jb_transport(fixture("jb_error_402.json"), status=402)
    out = jblanked.try_fetch(db, FRI_EVENING, transport=rec.transport)
    assert out["status"] == "refused" and out["http_status"] == 402
    run = db.scalar(select(FeedRun).where(FeedRun.feed == "jblanked"))
    assert run.status == "error" and run.made_request is True and run.http_status == 402
    assert "not have enough credits" in run.error and KEY not in run.error
    assert jblanked.try_fetch(db, FRI_EVENING + timedelta(minutes=6), transport=rec.transport)["status"] == (
        "budget_used"
    )


def test_intraday_call_after_a_release_only_with_spare_budget(db, jb_key, monkeypatch):
    load_ff(db)
    after_nfp = datetime(2026, 11, 6, 13, 40, tzinfo=UTC)
    assert jblanked.reason_due(db, after_nfp) is None  # budget 1 is kept for the evening
    monkeypatch.setattr(get_settings(), "jblanked_daily_requests", 3)
    assert jblanked.reason_due(db, after_nfp) == "after_release"
    assert jblanked.reason_due(db, datetime(2026, 11, 6, 13, 51, tzinfo=UTC)) is None  # > 20 min after
    assert jblanked.try_fetch(db, after_nfp, transport=jb_transport().transport)["status"] == "ok"
    assert jblanked.reason_due(db, after_nfp + timedelta(minutes=6)) is None  # already asked
    assert jblanked.reason_due(db, FRI_EVENING) == "evening"


def test_short_or_missing_key_means_not_configured_and_no_request(db, monkeypatch):
    rec = jb_transport()
    monkeypatch.setattr(get_settings(), "jblanked_api_key", None)
    assert jblanked.try_fetch(db, FRI_EVENING, transport=rec.transport)["status"] == "not_configured"
    monkeypatch.setattr(get_settings(), "jblanked_api_key", "too-short")
    out = jblanked.try_fetch(db, FRI_EVENING, transport=rec.transport)
    assert out["status"] == "not_configured" and "30+" in out["error"]
    assert jblanked.reason_due(db, FRI_EVENING) is None
    assert rec.requests == [] and db.scalar(select(func.count(FeedRun.id))) == 0


def test_a_failing_feed_is_logged_and_the_other_still_fills_the_calendar(db, jb_key):
    out = jobs.refresh_feeds(
        db,
        FRI_EVENING,
        live=True,
        ff_transport=ff_transport(status=500).transport,
        jb_transport=jb_transport().transport,
    )
    assert out["forex_factory"]["status"] == "error" and out["jblanked"]["status"] == "ok"
    ffrun = db.scalar(select(FeedRun).where(FeedRun.feed == "forex_factory"))
    assert ffrun.status == "error" and ffrun.http_status == 500 and "HTTP 500" in ffrun.error
    # No Forex Factory figures to copy the unit from, so the number is stored as JBlanked sent it.
    assert event(db, "USD", "Non-Farm Employment Change").actual == "254"


def test_a_feed_that_changed_shape_is_an_error_not_a_crash(db):
    out = ff.fetch(db, FRI_MORNING, Recorder(default=(200, {"unexpected": True})).transport)
    assert out["status"] == "error"
    assert "changed shape" in db.scalar(select(FeedRun.error))


def test_feeds_off_does_nothing(db):
    assert jobs.refresh_feeds(db, FRI_EVENING) == {"skipped": "feeds off"}  # tests run with feeds off
    assert db.scalar(select(func.count(FeedRun.id))) == 0


def test_coverage_ranges_merge_when_adjacent_or_overlapping(db):
    store.record_coverage(db, "jblanked", date(2026, 1, 1), date(2026, 1, 31))
    store.record_coverage(db, "jblanked", date(2026, 2, 1), date(2026, 2, 28))  # adjacent
    store.record_coverage(db, "jblanked", date(2026, 2, 20), date(2026, 3, 5))  # overlapping
    store.record_coverage(db, "jblanked", date(2026, 5, 1), date(2026, 5, 1))  # separate
    store.record_coverage(db, "forex_factory", date(2026, 3, 6), date(2026, 3, 12))
    db.commit()
    by_source = [(c["source"], c["start_date"], c["end_date"]) for c in store.coverage_by_source(db)]
    assert by_source == [
        ("forex_factory", date(2026, 3, 6), date(2026, 3, 12)),
        ("jblanked", date(2026, 1, 1), date(2026, 3, 5)),
        ("jblanked", date(2026, 5, 1), date(2026, 5, 1)),
    ]
    assert store.coverage_ranges(db) == [
        (date(2026, 1, 1), date(2026, 3, 12)),
        (date(2026, 5, 1), date(2026, 5, 1)),
    ]


# ---- backfill -------------------------------------------------------------------------------------


class Clock:
    def __init__(self, start: datetime):
        self.now = start
        self.slept = 0.0

    def __call__(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)
        self.slept += seconds


def test_backfill_loads_month_by_month_waits_for_the_slot_and_resumes(db, jb_key, monkeypatch):
    monkeypatch.setattr(get_settings(), "jblanked_daily_requests", 5)
    clock = Clock(datetime(2026, 11, 6, 9, 0, tzinfo=UTC))
    rec = Recorder(routes={"from=2026-09-01": (200, fixture("jb_range_2026-09.json"))}, default=(200, []))
    lines: list[str] = []
    out = backfill.run(
        db, start=date(2026, 8, 1), max_requests=2, now_fn=clock, sleep=clock.sleep, echo=lines.append,
        transport=rec.transport,
    )  # fmt: skip
    assert out == {"status": "paused", "requests": 2, "events": 3}
    assert [r.url.params["from"] for r in rec.requests] == ["2026-08-01", "2026-09-01"]
    assert rec.requests[0].url.path == "/news/api/forex-factory/calendar/range/"
    assert clock.slept >= 300  # waited for the 5-minute slot between the two requests
    assert any("waiting" in line for line in lines)
    assert db.get(AppState, "news_backfill").value == {"start": "2026-08-01", "next": "2026-10-01"}
    nfp = event(db, "USD", "Non-Farm Employment Change")
    assert nfp.at == datetime(2026, 9, 4, 12, 30, tzinfo=UTC) and nfp.actual == "22"
    # Resume: October, then November up to yesterday (5 Nov).
    out = backfill.run(
        db, start=date(2026, 8, 1), max_requests=5, now_fn=clock, sleep=clock.sleep, echo=lines.append,
        transport=rec.transport,
    )  # fmt: skip
    assert out["status"] == "done" and out["requests"] == 2
    assert [(r.url.params["from"], r.url.params["to"]) for r in rec.requests[2:]] == [
        ("2026-10-01", "2026-10-31"),
        ("2026-11-01", "2026-11-05"),
    ]
    cov = [c for c in store.coverage_by_source(db) if c["source"] == "jblanked"]
    assert [(c["start_date"], c["end_date"]) for c in cov] == [(date(2026, 8, 1), date(2026, 11, 5))]
    assert "JBlanked history coverage: 2026-08-01 to 2026-11-05" in lines[-1]


def test_backfill_stops_cleanly_without_credits_or_key(db, jb_key, monkeypatch):
    monkeypatch.setattr(get_settings(), "jblanked_daily_requests", 5)
    clock = Clock(datetime(2026, 11, 6, 9, 0, tzinfo=UTC))
    lines: list[str] = []
    rec = Recorder(default=(402, fixture("jb_error_402.json")))
    out = backfill.run(db, start=date(2026, 9, 1), now_fn=clock, sleep=clock.sleep, echo=lines.append,
                       transport=rec.transport)  # fmt: skip
    assert out["status"] == "refused" and out["requests"] == 1
    assert any("credits" in line for line in lines)
    assert db.get(AppState, "news_backfill") is None  # nothing loaded, so the cursor didn't move
    monkeypatch.setattr(get_settings(), "jblanked_api_key", "")
    lines.clear()
    out = backfill.run(db, now_fn=clock, sleep=clock.sleep, echo=lines.append, transport=rec.transport)
    assert out["status"] == "not_configured" and "JBLANKED_API_KEY" in lines[0]


def test_backfill_respects_the_shared_daily_budget(db, jb_key):
    clock = Clock(FRI_EVENING)
    jblanked.try_fetch(db, FRI_EVENING, transport=jb_transport().transport)  # the day's one request
    lines: list[str] = []
    out = backfill.run(db, start=date(2026, 9, 1), now_fn=clock, sleep=clock.sleep, echo=lines.append,
                       transport=jb_transport([]).transport)  # fmt: skip
    assert out["status"] == "budget_used" and out["requests"] == 0
    assert "daily budget" in lines[0]
