"""Trade news tags (inside / outside / no data), re-tagging, the analytics News filter and "Around news"."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import AppState, Event, EventType, Trade
from app.services import market_prefs
from app.services.news import store, tagging
from tests.test_journal_api import new_strategy

NFP_AT = datetime(2026, 11, 6, 13, 30, tzinfo=UTC)
ZEW_AT = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


def add_event(db, key: str, title: str, currency: str, at: datetime, impact: str = "high") -> Event:
    et = db.scalar(select(EventType).where(EventType.key == key))
    ev = Event(title=title, currency=currency, at=at, impact=impact, event_type_id=et.id, sources=["test"])
    db.add(ev)
    db.commit()
    return ev


@pytest.fixture
def news_week(db):
    """NFP (USD) and German ZEW (EUR), a medium USD event, and coverage for the week of 1–7 Nov 2026."""
    add_event(db, "USD:nfp", "Non-Farm Employment Change", "USD", NFP_AT)
    add_event(db, "EUR:german_zew", "German ZEW Economic Sentiment", "EUR", ZEW_AT)
    add_event(
        db, "USD:jolts", "JOLTS Job Openings", "USD", datetime(2026, 11, 3, 15, 0, tzinfo=UTC), "medium"
    )
    store.record_coverage(db, "forex_factory", date(2026, 11, 1), date(2026, 11, 7))
    db.commit()


def log_trade(client, strategy_id: int, instrument: str, opened: datetime, **extra) -> dict:
    body = {
        "kind": "backtest",
        "instrument": instrument,
        "side": "buy",
        "opened_at": opened.isoformat(),
        "closed_at": (opened + timedelta(minutes=30)).isoformat(),
        "r_multiple": extra.pop("r", 1.0),
        "pnl": extra.pop("pnl", 100.0),
        **extra,
    }
    res = client.post(f"/api/strategies/{strategy_id}/trades", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def test_trades_are_tagged_when_logged(admin_client, news_week):
    s = new_strategy(admin_client)
    inside = log_trade(admin_client, s["id"], "NAS100", NFP_AT + timedelta(minutes=10))
    assert inside["news_impact"] == "high" and inside["news_status"] == "inside"
    assert inside["news_events"] == [
        {
            "event_id": inside["news_events"][0]["event_id"],
            "name": "Non-Farm Payrolls",
            "currency": "USD",
            "at": "2026-11-06T13:30:00Z",
            "minutes_from_entry": -10,
        }
    ]
    edge = log_trade(admin_client, s["id"], "NAS100", NFP_AT - timedelta(minutes=15))
    assert edge["news_status"] == "inside" and edge["news_events"][0]["minutes_from_entry"] == 15
    outside = log_trade(admin_client, s["id"], "NAS100", NFP_AT + timedelta(minutes=16))
    assert outside["news_impact"] == "none" and outside["news_status"] == "outside"
    assert outside["news_events"] == []
    # Medium-impact events never open a window.
    jolts = log_trade(admin_client, s["id"], "NAS100", datetime(2026, 11, 3, 15, 0, tzinfo=UTC))
    assert jolts["news_status"] == "outside"
    # Outside news coverage: no data rather than a guess.
    old = log_trade(admin_client, s["id"], "NAS100", datetime(2026, 9, 10, 13, 30, tzinfo=UTC))
    assert old["news_impact"] is None and old["news_status"] == "no_data" and old["news_events"] == []


def test_instrument_mapping_decides_which_events_count(admin_client, news_week):
    s = new_strategy(admin_client, instruments=["GER40", "NAS100"])
    # GER40 ← EUR (and DE), not USD: NFP doesn't touch it, the German ZEW does.
    ger_nfp = log_trade(admin_client, s["id"], "GER40", NFP_AT + timedelta(minutes=5))
    assert ger_nfp["news_status"] == "outside"
    ger_zew = log_trade(admin_client, s["id"], "GER40", ZEW_AT + timedelta(minutes=5))
    assert (
        ger_zew["news_status"] == "inside"
        and ger_zew["news_events"][0]["name"] == "German ZEW Economic Sentiment"
    )
    nas_zew = log_trade(admin_client, s["id"], "NAS100", ZEW_AT + timedelta(minutes=5))
    assert nas_zew["news_status"] == "outside"
    # The instrument alias resolves first (US100 → NAS100 ← USD).
    alias = log_trade(admin_client, s["id"], "US100", NFP_AT)
    assert alias["instrument"] == "NAS100" and alias["news_status"] == "inside"


def test_window_is_the_trade_owners_and_a_window_change_retags(
    admin, admin_client, member_client, db, news_week
):
    s = new_strategy(admin_client)
    t = log_trade(admin_client, s["id"], "NAS100", NFP_AT + timedelta(minutes=25))
    assert t["news_status"] == "outside"
    res = admin_client.patch("/api/news/prefs", json={"news_window_minutes": 30})
    assert res.status_code == 200 and res.json()["news_window_minutes"] == 30
    assert admin_client.get(f"/api/trades/{t['id']}").json()["news_status"] == "inside"
    # Another user's window never changes my trades.
    assert member_client.patch("/api/news/prefs", json={"news_window_minutes": 0}).status_code == 200
    assert admin_client.get(f"/api/trades/{t['id']}").json()["news_status"] == "inside"
    admin_client.patch("/api/news/prefs", json={"news_window_minutes": 0})
    exact = log_trade(admin_client, s["id"], "NAS100", NFP_AT)
    assert exact["news_status"] == "inside"
    assert admin_client.get(f"/api/trades/{t['id']}").json()["news_status"] == "outside"


def test_editing_the_entry_time_retags(admin_client, news_week):
    s = new_strategy(admin_client)
    t = log_trade(admin_client, s["id"], "NAS100", NFP_AT + timedelta(hours=2))
    assert t["news_status"] == "outside"
    moved = admin_client.patch(
        f"/api/trades/{t['id']}", json={"opened_at": (NFP_AT - timedelta(minutes=3)).isoformat()}
    )
    assert moved.json()["news_status"] == "inside"


def test_imported_trades_are_tagged(admin_client, db):
    from tests.test_journal_api import do_import

    s = new_strategy(admin_client)
    store.record_coverage(db, "jblanked", date(2020, 1, 1), date(2030, 1, 1))
    db.commit()
    do_import(admin_client, s["id"], "backtest")
    statuses = {t.news_impact for t in db.scalars(select(Trade).where(Trade.strategy_id == s["id"]))}
    assert statuses == {"none"}  # covered, and no events stored near them


def test_retag_when_coverage_grows(admin_client, db, news_week):
    s = new_strategy(admin_client)
    sept = log_trade(admin_client, s["id"], "NAS100", datetime(2026, 9, 4, 12, 40, tzinfo=UTC))
    assert sept["news_status"] == "no_data"
    first = tagging.retag_if_coverage_grew(db, NOW)
    assert db.get(AppState, tagging.STATE_KEY).value["fingerprint"]
    assert tagging.retag_if_coverage_grew(db, NOW + timedelta(minutes=1)) == {"retagged": 0}  # cheap no-op
    assert first["retagged"] == 0
    # A backfill brings September's NFP and coverage: the trade is now inside its window.
    add_event(db, "USD:nfp", "Non-Farm Employment Change", "USD", datetime(2026, 9, 4, 12, 30, tzinfo=UTC))
    store.record_coverage(db, "jblanked", date(2026, 9, 1), date(2026, 9, 30))
    db.commit()
    assert tagging.retag_if_coverage_grew(db, NOW + timedelta(minutes=2)) == {"retagged": 1}
    t = admin_client.get(f"/api/trades/{sept['id']}").json()
    assert t["news_status"] == "inside" and t["news_events"][0]["minutes_from_entry"] == -10


def test_instrument_map_edit_retags_every_trade(admin_client, db, news_week):
    s = new_strategy(admin_client)
    t = log_trade(admin_client, s["id"], "NAS100", NFP_AT)
    assert t["news_status"] == "inside"
    original = admin_client.get("/api/news/instrument-map").json()
    try:
        trimmed = [r for r in original if not (r["currency"] == "USD" and r["instrument"] == "NAS100")]
        assert admin_client.put("/api/news/instrument-map", json=trimmed).status_code == 200
        assert admin_client.get(f"/api/trades/{t['id']}").json()["news_status"] == "outside"
    finally:
        admin_client.put("/api/news/instrument-map", json=original)
    assert admin_client.get(f"/api/trades/{t['id']}").json()["news_status"] == "inside"
    assert market_prefs.instruments_for(db, "USD") == ["XAUUSD", "BTCUSD", "EURUSD", "NAS100"]


# ---- analytics -----------------------------------------------------------------------------------


def query(client, **body) -> dict:
    res = client.post("/api/analytics/query", json=body)
    assert res.status_code == 200, res.text
    return res.json()


@pytest.fixture
def tagged_strategy(admin_client, news_week):
    s = new_strategy(admin_client, instruments=["NAS100", "GER40"])
    log_trade(admin_client, s["id"], "NAS100", NFP_AT + timedelta(minutes=5), r=2.0, pnl=200)  # inside NFP
    log_trade(admin_client, s["id"], "NAS100", NFP_AT - timedelta(minutes=5), r=-1.0, pnl=-100)  # inside NFP
    log_trade(admin_client, s["id"], "GER40", ZEW_AT, r=3.0, pnl=300)  # inside ZEW
    log_trade(admin_client, s["id"], "NAS100", NFP_AT + timedelta(hours=3), r=1.0, pnl=100)  # outside
    log_trade(
        admin_client, s["id"], "NAS100", datetime(2026, 9, 10, 9, 0, tzinfo=UTC), r=-1.0, pnl=-100
    )  # no data
    return s


def test_analytics_news_filter_is_live(admin_client, tagged_strategy):
    sid = tagged_strategy["id"]
    out = query(admin_client, strategy_id=sid)
    assert out["news_status"] == "partial" and "4 of 5 trades" in out["notes"]["news"]
    assert query(admin_client, strategy_id=sid, filters={"news": "inside"})["counts"]["filtered"] == 3
    assert query(admin_client, strategy_id=sid, filters={"news": "outside"})["counts"]["filtered"] == 1
    assert query(admin_client, strategy_id=sid, filters={"news": "no_data"})["counts"]["filtered"] == 1
    nfp_only = query(admin_client, strategy_id=sid, filters={"news_event_types": ["Non-Farm Payrolls"]})
    assert nfp_only["counts"]["filtered"] == 2
    both = query(
        admin_client,
        strategy_id=sid,
        filters={"news_event_types": ["non-farm payrolls", "German ZEW Economic Sentiment"]},
    )
    assert both["counts"]["filtered"] == 3
    in_range = query(admin_client, strategy_id=sid, filters={"date_from": "2026-11-01"})
    assert in_range["news_status"] == "partial"  # status is over the trades in scope, before filters


def test_around_news_breakdown(admin_client, tagged_strategy):
    out = query(admin_client, strategy_id=tagged_strategy["id"])
    groups = {g["key"]: g for g in out["backtest"]["around_news"]}
    assert [g["key"] for g in out["backtest"]["around_news"]][:3] == [
        "Inside news window",
        "Outside",
        "No news data",
    ]
    inside = groups["Inside news window"]
    assert inside["trades"] == 3 and inside["total_r"] == pytest.approx(4.0)
    assert inside["win_rate"] == pytest.approx(2 / 3, abs=1e-3) and inside["avg_r"] == pytest.approx(
        4 / 3, abs=1e-3
    )
    assert groups["Outside"]["trades"] == 1 and groups["No news data"]["trades"] == 1
    assert groups["Non-Farm Payrolls"]["trades"] == 2 and groups["Non-Farm Payrolls"][
        "total_r"
    ] == pytest.approx(1.0)
    assert groups["German ZEW Economic Sentiment"]["trades"] == 1
    assert set(inside) == {"key", "trades", "win_rate", "avg_r", "total_r"}


def test_ideal_block_has_around_news_and_everything_known_is_ok(admin_client, news_week):
    s = new_strategy(admin_client)
    log_trade(admin_client, s["id"], "NAS100", NFP_AT, kind="ideal")
    out = query(admin_client, source="ideal", strategy_id=s["id"])
    assert out["news_status"] == "ok" and out["notes"]["news"] is None
    assert out["ideal"]["around_news"][0] == {
        "key": "Inside news window",
        "trades": 1,
        "win_rate": 1.0,
        "avg_r": 1.0,
        "total_r": 1.0,
    }


def test_csv_export_carries_the_news_tags(admin_client, tagged_strategy):
    import csv
    import io
    import json

    q = json.dumps({"strategy_id": tagged_strategy["id"], "filters": {"news": "inside"}})
    res = admin_client.get("/api/analytics/export/csv", params={"q": q})
    assert res.status_code == 200
    rows = list(csv.DictReader(io.StringIO(res.text.lstrip("\ufeff"))))
    assert len(rows) == 3 and {r["news"] for r in rows} == {"inside"}
    assert {r["news_events"] for r in rows} == {"Non-Farm Payrolls", "German ZEW Economic Sentiment"}
