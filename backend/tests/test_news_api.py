"""Every /api/news endpoint, with time frozen, plus the dev seed's synthetic news."""

import re
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.api import news as news_api
from app.models import Event, EventType, PriceReaction
from app.services.journal_rules import to_uk
from app.services.news import jblanked, store, synthetic
from tests.test_news_feeds import FF_WEEK, KEY, Recorder, jb_transport, load_ff

THU = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)  # Thursday 5 Nov, 09:00 UK
FRI_NOON = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)


@pytest.fixture
def frozen(monkeypatch):
    """Freeze the API's clock: `frozen(datetime)`."""

    def set_now(now: datetime) -> None:
        monkeypatch.setattr(news_api, "utcnow", lambda: now)

    set_now(FRI_NOON)
    return set_now


@pytest.fixture
def week(db):
    load_ff(db, datetime(2026, 11, 2, 9, 0, tzinfo=UTC))


def get(client, url, **params):
    res = client.get(url, params=params)
    assert res.status_code == 200, res.text
    return res.json()


def test_every_endpoint_needs_a_signed_in_user(client):
    for url in (
        "/api/news/status",
        "/api/news/events",
        "/api/news/events/1",
        "/api/news/today",
        "/api/news/next",
        "/api/news/week-ahead",
        "/api/news/timeline",
        "/api/news/prefs",
        "/api/news/instrument-map",
    ):
        assert client.get(url).status_code == 401, url


def test_events_default_to_today_with_filters(member_client, frozen, week):
    out = get(member_client, "/api/news/events")
    assert out["from"] == out["to"] == "2026-11-06"
    assert out["window_minutes"] == 15 and "NAS100" in out["my_instruments"]
    titles = [e["title"] for e in out["events"]]
    assert titles[:4] == [
        "Non-Farm Employment Change",
        "Unemployment Rate",
        "Average Hourly Earnings m/m",
        "Employment Change",
    ]
    nfp = out["events"][0]
    assert nfp | {"id": 0, "event_type_id": 0} == {
        "id": 0,
        "title": "Non-Farm Employment Change",
        "name": "Non-Farm Payrolls",
        "currency": "USD",
        "at": "2026-11-06T13:30:00Z",
        "uk_date": "2026-11-06",
        "uk_time": "13:30",
        "all_day": False,
        "impact": "high",
        "impact_label": "High",
        "forecast": "110K",
        "previous": "22K",
        "actual": None,
        "revised": None,
        "released": False,
        "surprise": None,
        "instruments": ["XAUUSD", "BTCUSD", "EURUSD", "NAS100"],
        "mine": True,
        "event_type_id": 0,
        "has_explanation": True,
    }
    week_all = get(member_client, "/api/news/events", **{"from": "2026-11-01", "to": "2026-11-07"})
    assert len(week_all["events"]) == 19
    usd_high = get(
        member_client, "/api/news/events", **{"from": "2026-11-01", "to": "2026-11-07"}, currencies="USD",
        impacts="high",
    )  # fmt: skip
    assert {e["currency"] for e in usd_high["events"]} == {"USD"}
    assert {e["impact"] for e in usd_high["events"]} == {"high"}
    assert len(usd_high["events"]) == 10
    member_client.patch("/api/news/prefs", json={"instruments": ["GER40"]})
    mine = get(member_client, "/api/news/events", **{"from": "2026-11-01", "to": "2026-11-07"}, mine=1)
    assert [e["title"] for e in mine["events"]] == ["German ZEW Economic Sentiment"]
    cny = next(e for e in week_all["events"] if e["currency"] == "CNY")
    assert cny["instruments"] == [] and cny["mine"] is False and cny["has_explanation"] is False
    assert member_client.get("/api/news/events", params={"impacts": "huge"}).status_code == 422


def test_released_event_has_surprise(member_client, frozen, week, db, monkeypatch):
    from app.core.settings import get_settings

    monkeypatch.setattr(get_settings(), "jblanked_api_key", KEY)
    jblanked.try_fetch(db, datetime(2026, 11, 6, 21, 30, tzinfo=UTC), transport=jb_transport().transport)
    out = get(member_client, "/api/news/events")
    by_title = {e["title"]: e for e in out["events"] if e["currency"] == "USD"}
    nfp = by_title["Non-Farm Employment Change"]
    assert nfp["released"] is True and nfp["actual"] == "254K"
    assert nfp["surprise"] == {
        "direction": "up",
        "diff": 144.0,
        "diff_text": "+144K",
        "better": True,
        "wording": "Better than forecast",
    }
    ur = by_title["Unemployment Rate"]
    assert ur["surprise"]["diff_text"] == "−0.1%" and ur["surprise"]["wording"] == "Better than forecast"
    ahe = by_title["Average Hourly Earnings m/m"]
    assert ahe["surprise"]["direction"] == "inline" and ahe["surprise"]["wording"] == "In line with forecast"


def test_today_headline(member_client, frozen, week):
    out = get(member_client, "/api/news/today")
    # Default instruments: USD and CAD high-impact events today (NFP, UR, AHE, CAD jobs, UoM, Powell).
    assert out["high_count"] == 6
    assert out["headline"] == "6 high-impact events today – USD Non-Farm Payrolls at 13:30"
    frozen(datetime(2026, 11, 6, 16, 0, tzinfo=UTC))
    assert get(member_client, "/api/news/today")["headline"].endswith("USD Fed Chair Speaks at 18:00")
    member_client.patch("/api/news/prefs", json={"instruments": ["GER40"]})
    quiet = get(member_client, "/api/news/today")
    assert quiet["headline"] == "No high-impact news today." and quiet["high_count"] == 0


def test_today_says_one_event_in_the_singular(member_client, frozen, week):
    frozen(datetime(2026, 11, 3, 8, 0, tzinfo=UTC))
    member_client.patch("/api/news/prefs", json={"instruments": ["GER40"]})
    out = get(member_client, "/api/news/today")
    assert out["headline"] == "1 high-impact event today – EUR German ZEW Economic Sentiment at 10:00"


def test_next_high_impact_event(member_client, frozen, week):
    frozen(datetime(2026, 11, 6, 13, 0, tzinfo=UTC))
    out = get(member_client, "/api/news/next")
    assert out["event"]["title"] == "Non-Farm Employment Change"
    assert out["seconds_until"] == 1800 and out["server_now"] == "2026-11-06T13:00:00Z"
    member_client.patch("/api/news/prefs", json={"instruments": ["GER40"]})
    assert get(member_client, "/api/news/next")["event"] is None
    everyone = get(member_client, "/api/news/next", mine=0)
    assert everyone["event"]["title"] == "Non-Farm Employment Change"
    frozen(datetime(2026, 11, 8, 12, 0, tzinfo=UTC))
    assert get(member_client, "/api/news/next", mine=0) == {
        "event": None,
        "seconds_until": None,
        "server_now": "2026-11-08T12:00:00Z",
    }


def test_week_ahead_rolls_to_next_week_once_the_trading_week_is_over(member_client, frozen, db):
    load_ff(db, datetime(2026, 10, 26, 9, 0, tzinfo=UTC), name="ff_week_2026-10-25.json")
    load_ff(db, datetime(2026, 11, 2, 9, 0, tzinfo=UTC), name=FF_WEEK)
    frozen(datetime(2026, 10, 30, 20, 59, tzinfo=UTC))  # Friday 20:59 UK: New York still open, this week
    out = get(member_client, "/api/news/week-ahead")
    assert (out["start"], out["end"], out["default_view"]) == ("2026-10-26", "2026-10-30", False)
    gdp = next(e for d in out["days"] for e in d["events"] if e["title"] == "Advance GDP q/q")
    assert gdp["uk_time"] == "12:30"  # the gap week
    for weekend in (datetime(2026, 10, 30, 21, 0, tzinfo=UTC), datetime(2026, 10, 31, 12, 0, tzinfo=UTC)):
        frozen(weekend)  # Friday 21:00 and Saturday UK: the coming week, not the one just finished
        out = get(member_client, "/api/news/week-ahead")
        assert (out["start"], out["default_view"]) == ("2026-11-02", False)
    frozen(datetime(2026, 11, 1, 18, 0, tzinfo=UTC))  # Sunday 18:00 UK: the week ahead is the default view
    out = get(member_client, "/api/news/week-ahead")
    assert (out["start"], out["end"], out["default_view"]) == ("2026-11-02", "2026-11-06", True)
    assert [d["label"] for d in out["days"]] == [
        "Mon 2 Nov",
        "Tue 3 Nov",
        "Wed 4 Nov",
        "Thu 5 Nov",
        "Fri 6 Nov",
    ]
    assert all(e["impact"] == "high" for d in out["days"] for e in d["events"])
    friday = out["days"][4]["events"]
    assert [e["title"] for e in friday][0] == "Non-Farm Employment Change" and len(friday) == 6
    # Monday's AUD Cash Rate is 22:30 New York on Monday = 03:30 UK on Tuesday.
    assert any(e["title"] == "Cash Rate" for e in out["days"][1]["events"])
    picked = get(member_client, "/api/news/week-ahead", start="2026-10-28")
    assert picked["start"] == "2026-10-26" and picked["default_view"] is False


def test_timeline_sessions_windows_and_bst(member_client, frozen, week):
    out = get(member_client, "/api/news/timeline", date="2026-11-06")
    assert out["window_minutes"] == 15
    assert out["sessions"] == [
        {"name": "Asia", "start": "2026-11-06T00:00:00Z", "end": "2026-11-06T08:00:00Z"},
        {"name": "London", "start": "2026-11-06T08:00:00Z", "end": "2026-11-06T16:30:00Z"},
        {"name": "New York", "start": "2026-11-06T13:30:00Z", "end": "2026-11-06T21:00:00Z"},
    ]
    nfp = next(e for e in out["events"] if e["title"] == "Non-Farm Employment Change")
    assert {"event_id": nfp["id"], "start": "2026-11-06T13:15:00Z", "end": "2026-11-06T13:45:00Z"} in out[
        "windows"
    ]
    assert len(out["windows"]) == 6
    member_client.patch("/api/news/prefs", json={"news_window_minutes": 30})
    wide = get(member_client, "/api/news/timeline", date="2026-11-06")
    assert wide["window_minutes"] == 30 and wide["windows"][0]["start"] == "2026-11-06T13:00:00Z"
    summer = get(member_client, "/api/news/timeline", date="2026-07-15")
    assert summer["sessions"][0] == {
        "name": "Asia",
        "start": "2026-07-14T23:00:00Z",
        "end": "2026-07-15T07:00:00Z",
    }
    assert summer["events"] == [] and summer["windows"] == []


def _cpi_with_reactions(db, ranges: list[float]) -> list[Event]:
    et = db.scalar(select(EventType).where(EventType.key == "USD:cpi_mm"))
    events = []
    for i, rng in enumerate(ranges):
        at = datetime(2026, 10 - i, 14, 12, 30, tzinfo=UTC)
        ev = Event(
            title="CPI m/m", currency="USD", at=at, impact="high", event_type_id=et.id, sources=["test"],
            forecast="0.3%", forecast_value=0.3, actual="0.4%", actual_value=0.4,
            previous="0.2%", previous_value=0.2,
        )  # fmt: skip
        db.add(ev)
        db.flush()
        for h, k in ((5, 0.5), (15, 1.0), (60, 1.6)):
            db.add(
                PriceReaction(
                    event_id=ev.id, instrument="XAUUSD", horizon_minutes=h, status="ok", range_units=rng * k,
                    move_units=rng * k / 2, direction="up", unit="points",
                )
            )  # fmt: skip
        db.add(
            PriceReaction(
                event_id=ev.id, instrument="EURUSD", horizon_minutes=15, status="unavailable", unit="pips",
            )
        )  # fmt: skip
        events.append(ev)
    db.commit()
    return events


def test_event_detail_with_history_reactions_and_summary(member_client, frozen, db):
    events = _cpi_with_reactions(db, [150.0, 180.0, 210.0])
    upcoming = Event(
        title="CPI m/m", currency="USD", at=datetime(2026, 11, 13, 13, 30, tzinfo=UTC), impact="high",
        event_type_id=events[0].event_type_id, sources=["test"], forecast="0.3%", forecast_value=0.3,
    )  # fmt: skip
    db.add(upcoming)
    db.commit()
    out = get(member_client, f"/api/news/events/{upcoming.id}")
    assert out["event"]["id"] == upcoming.id and out["event"]["released"] is False
    assert out["type"]["name"] == "CPI m/m" and out["type"]["higher_is_better"] is True
    assert out["type"]["explanation"] and out["type"]["why_it_matters"]
    assert [h["event_id"] for h in out["history"]] == [e.id for e in events]  # newest first, past only
    assert out["history"][0]["surprise"]["wording"] == "Better than forecast"
    gold = next(r for r in out["reactions"] if r["instrument"] == "XAUUSD")
    assert gold["unit"] == "points" and gold["releases"] == 3
    assert gold["average_range"] == {"5": 90.0, "15": 180.0, "60": 288.0}
    assert gold["rows"][0]["horizons"]["15"] == {
        "status": "ok",
        "range": 150.0,
        "move": 75.0,
        "direction": "up",
    }
    eur = next(r for r in out["reactions"] if r["instrument"] == "EURUSD")
    assert eur["average_range"]["15"] is None and eur["rows"][0]["horizons"]["5"]["status"] == "none"
    assert out["summary"] == (
        "US CPI m/m: XAUUSD has averaged a 180-point range in the first 15 minutes over the last 3 releases."
    )
    assert out["empty"] == {"history": None, "reactions": None}


def test_event_detail_empty_texts_are_honest(member_client, frozen, week, db):
    powell = db.scalar(select(Event).where(Event.title == "Fed Chair Powell Speaks"))
    out = get(member_client, f"/api/news/events/{powell.id}")
    assert out["history"] == [] and out["reactions"] == [] and out["summary"] is None
    assert out["empty"]["history"].startswith("No past releases stored yet")
    assert out["empty"]["reactions"].startswith("No price reactions stored yet")
    waller = db.scalar(select(Event).where(Event.title == "FOMC Member Waller Speaks"))
    unseeded = get(member_client, f"/api/news/events/{waller.id}")
    assert unseeded["type"]["explanation"] is None and unseeded["event"]["has_explanation"] is False
    assert member_client.get("/api/news/events/999999").status_code == 404


def test_status_reports_feeds_coverage_and_jblanked(member_client, frozen, db, monkeypatch):
    from app.core.settings import get_settings

    out = get(member_client, "/api/news/status")
    assert out["last_updated_at"] is None and out["coverage"] == []
    assert out["jblanked"] == {
        "configured": False,
        "requests_today": 0,
        "daily_budget": 1,
        "next_slot_at": None,
    }
    feeds = {f["feed"] for f in out["feeds"]}
    assert feeds == {"forex_factory", "forex_factory_next", "jblanked", "backfill"}
    load_ff(db, datetime(2026, 11, 6, 11, 0, tzinfo=UTC))
    monkeypatch.setattr(get_settings(), "jblanked_api_key", KEY)
    jblanked.try_fetch(
        db, FRI_NOON - timedelta(minutes=2), transport=Recorder(default=(500, {"detail": "down"})).transport
    )
    out = get(member_client, "/api/news/status")
    ffs = next(f for f in out["feeds"] if f["feed"] == "forex_factory")
    jbs = next(f for f in out["feeds"] if f["feed"] == "jblanked")
    assert ffs["last_status"] == "ok" and ffs["last_success_at"] == "2026-11-06T11:00:00Z"
    assert (
        jbs["last_status"] == "error"
        and jbs["last_error"] == "HTTP 500: down"
        and jbs["last_success_at"] is None
    )
    assert out["last_updated_at"] == "2026-11-06T11:00:00Z"
    assert out["coverage"] == [
        {"source": "forex_factory", "start_date": "2026-11-01", "end_date": "2026-11-07"}
    ]
    assert out["jblanked"] == {
        "configured": True,
        "requests_today": 1,
        "daily_budget": 1,
        "next_slot_at": "2026-11-06T12:03:00Z",
    }


def test_prefs_validate_and_round_trip(member_client):
    out = get(member_client, "/api/news/prefs")
    assert out["news_window_minutes"] == 15 and "XAUUSD" in out["instruments"]
    assert {"code": "GER40", "name": "Germany 40"} in out["available"]
    res = member_client.patch("/api/news/prefs", json={"instruments": ["xauusd", "GER40", "XAUUSD"]})
    assert res.status_code == 200 and res.json()["instruments"] == ["XAUUSD", "GER40"]
    assert member_client.patch("/api/news/prefs", json={"instruments": ["DOGEUSD"]}).status_code == 422
    assert member_client.patch("/api/news/prefs", json={"news_window_minutes": 121}).status_code == 422
    assert member_client.patch("/api/news/prefs", json={"news_window_minutes": -1}).status_code == 422
    res = member_client.patch("/api/news/prefs", json={"news_window_minutes": 120})
    assert res.json() | {"available": []} == {
        "instruments": ["XAUUSD", "GER40"],
        "news_window_minutes": 120,
        "available": [],
    }


def test_instrument_map_is_admin_only_to_change(member_client, admin_client):
    rows = get(member_client, "/api/news/instrument-map")
    assert {"currency": "EUR", "instrument": "GER40"} in rows and {
        "currency": "USD",
        "instrument": "NAS100",
    } in rows
    assert member_client.put("/api/news/instrument-map", json=rows).status_code == 403
    try:
        bad = admin_client.put("/api/news/instrument-map", json=[{"currency": "USD", "instrument": "NOPE"}])
        assert bad.status_code == 422
        res = admin_client.put(
            "/api/news/instrument-map", json=[*rows, {"currency": "cny", "instrument": "audusd"}]
        )
        assert res.status_code == 200 and {"currency": "CNY", "instrument": "AUDUSD"} in res.json()
    finally:
        assert admin_client.put("/api/news/instrument-map", json=rows).status_code == 200
    assert get(member_client, "/api/news/instrument-map") == rows


def test_strategy_brief_lists_next_months_news(admin_client, db, week):
    from tests.test_journal_api import new_strategy

    s = new_strategy(admin_client, instruments=["GER40"])
    body = {
        "kind": "ideal", "instrument": "GER40", "side": "buy", "opened_at": "2026-10-20T09:00:00Z",
        "entry_price": 20000, "initial_sl": 19950, "exit_price": 20100, "pnl": 100,
    }  # fmt: skip
    assert admin_client.post(f"/api/strategies/{s['id']}/trades", json=body).status_code == 201
    brief = admin_client.get(f"/api/strategies/{s['id']}/brief").json()
    news = brief["news"]
    assert brief["next_uncovered"] == "2026-11" and news["month"] == "2026-11"
    assert news["status"] == "partial" and "7 of 30 days" in news["note"]
    assert [e["title"] for e in news["events"]] == ["German ZEW Economic Sentiment"] and news[
        "high_count"
    ] == 1
    store.record_coverage(db, "jblanked", date(2026, 11, 1), date(2026, 11, 30))
    db.commit()
    news = admin_client.get(f"/api/strategies/{s['id']}/brief").json()["news"]
    assert news["status"] == "ok" and news["note"] == "1 high-impact event in November 2026."


# ---- the dev seed's synthetic news ----------------------------------------------------------------


def test_synthetic_week_has_what_the_smoke_suite_needs(db):
    now = datetime(2026, 11, 4, 10, 7, tzinfo=UTC)  # Wednesday
    out = synthetic.seed(db, now)
    assert out["week"] >= 40 and out["history"] >= 20 and out["reactions"] == out["history"] * 6
    upcoming = list(
        db.scalars(select(Event).where(Event.impact == "high", Event.at > now).order_by(Event.at))
    )
    assert any(e.at <= now + timedelta(hours=2) for e in upcoming)
    today = [e for e in upcoming if to_uk(e.at).date() == to_uk(now).date()]
    assert any(e.at > now + timedelta(hours=2) for e in today)
    past = list(db.scalars(select(Event).where(Event.at < now, Event.actual.is_not(None))))
    beats = [e for e in past if e.forecast_value is not None and e.actual_value > e.forecast_value]
    misses = [e for e in past if e.forecast_value is not None and e.actual_value < e.forecast_value]
    assert beats and misses
    unseeded = db.scalar(
        select(func.count(Event.id))
        .join(EventType)
        .where(EventType.seeded.is_(False), Event.impact == "high")
    )
    assert unseeded == 0  # every high-impact title matches a seeded type
    assert store.covered(store.coverage_ranges(db), date(2026, 1, 15))
    cpi = db.scalar(
        select(Event).where(Event.title == "CPI m/m", Event.currency == "USD").order_by(Event.at.desc())
    )
    pattern = (
        r"^US CPI m/m: XAUUSD has averaged a [\d,]+-point range in the first 15 minutes "
        r"over the last \d+ releases\.$"
    )
    assert re.match(pattern, _summary(db, cpi.id) or "")


def _summary(db, event_id: int) -> str | None:
    from app.models import User
    from app.services.news import queries

    user = User(id=0, email="x@example.test", display_name="X", role="member")
    return queries.detail(db, user, event_id, datetime(2026, 11, 4, 10, 7, tzinfo=UTC))["summary"]


def test_seed_dev_style_flow_tags_trades(db, admin_client):
    from app.services.news import tagging
    from tests.test_journal_api import new_strategy

    s = new_strategy(admin_client)
    now = datetime(2026, 11, 4, 10, 7, tzinfo=UTC)
    synthetic.seed(db, now)
    body = {
        "kind": "backtest",
        "instrument": "NAS100",
        "side": "buy",
        "opened_at": "2026-06-10T09:00:00Z",
        "pnl": 50,
    }
    tid = admin_client.post(f"/api/strategies/{s['id']}/trades", json=body).json()["id"]
    tagging.retag(db)
    assert admin_client.get(f"/api/trades/{tid}").json()["news_status"] == "outside"


def test_events_carry_bank_holidays_and_how_far_the_schedule_reaches(member_client, frozen, db):
    load_ff(db, datetime(2026, 11, 2, 9, 0, tzinfo=UTC), name=FF_WEEK)
    frozen(datetime(2026, 11, 7, 12, 0, tzinfo=UTC))
    out = get(member_client, "/api/news/events", **{"from": "2026-11-23", "to": "2026-11-27"})
    assert out["schedule_through"] == "2026-11-07"  # nothing published for that week yet
    thanksgiving = [h for h in out["holidays"] if h["currency"] == "USD"]
    assert thanksgiving == [
        {"date": "2026-11-26", "currency": "USD", "centre": "United States", "name": "Thanksgiving Day"}
    ]
    assert any(h["currency"] == "JPY" and h["date"] == "2026-11-23" for h in out["holidays"])
    span = {"from": "2026-12-21", "to": "2026-12-31"}
    only_gbp = get(member_client, "/api/news/events", **span, currencies="GBP")
    assert {h["currency"] for h in only_gbp["holidays"]} == {"GBP"}
    # Boxing Day falls on a Saturday, so the weekday holiday is the observed Monday
    assert [h["date"] for h in only_gbp["holidays"]] == ["2026-12-25", "2026-12-28"]


def test_week_ahead_days_list_their_bank_holidays(member_client, frozen):
    frozen(datetime(2026, 11, 21, 12, 0, tzinfo=UTC))  # Saturday: the coming week is Thanksgiving week
    out = get(member_client, "/api/news/week-ahead")
    assert out["start"] == "2026-11-23"
    thursday = out["days"][3]
    assert thursday["date"] == "2026-11-26"
    assert any(h["name"] == "Thanksgiving Day" for h in thursday["holidays"])
