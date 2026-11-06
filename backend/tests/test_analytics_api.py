"""POST /api/analytics/query: sources, filters, scope, permissions, reconcile and speed."""

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.models import Strategy, User
from app.services.analytics.synthetic import insert_trades, trade_dicts
from tests.conftest import FIXTURES
from tests.test_journal_api import do_import, new_strategy

SAMPLE = (FIXTURES / "fxreplay-sample.csv").read_bytes()
REAL_SAMPLE = Path(__file__).resolve().parents[2] / "Samples" / "02:11:26 Backtest x8 Trades.csv"


def query(client, **body):
    res = client.post("/api/analytics/query", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def seeded(db, user: User, n: int, *, kind="backtest", seed=7, name="Synthetic") -> Strategy:
    s = Strategy(
        owner_id=user.id, name=name, rules=[{"key": f"r{i}", "text": f"Rule {i}"} for i in (1, 2, 3, 4)]
    )
    db.add(s)
    db.commit()
    insert_trades(db, trade_dicts(s, user.id, n, kind=kind, seed=seed))
    return s


def test_backtest_query_returns_kpis_series_and_registry(admin_client):
    s = new_strategy(admin_client)
    do_import(admin_client, s["id"], "backtest")
    out = query(admin_client, source="backtest", strategy_id=s["id"])
    assert out["counts"]["backtest"] == 10
    k = out["backtest"]["kpis"]
    assert k["trades"] == 10
    assert k["wins"] + k["losses"] + k["breakevens"] == 10
    assert len(out["backtest"]["equity"]) == 10
    assert out["backtest"]["equity"][-1]["cum_r"] == pytest.approx(k["total_r"], abs=1e-3)
    assert {"hour", "weekday", "session", "entry_model", "instrument", "direction"} <= set(
        out["backtest"]["breakdowns"]
    )
    assert out["registry"] and all("formula" in m for m in out["registry"])
    assert out["ideal"] is None and out["compare"] is None
    assert out["news_status"] == "no_data" and out["notes"]["news"] == "No news data"
    assert len(out["backtest"]["r_sequence"]) == 10
    # FX Replay's idealTP gives a favourable excursion, so exit efficiency works on imported trades.
    assert out["backtest"]["excursions"]["n"] == 10
    assert k["exit_efficiency"] is not None


def test_ideal_and_compare_sources(admin_client):
    s = new_strategy(admin_client)
    do_import(admin_client, s["id"], "ideal")
    do_import(admin_client, s["id"], "backtest")
    ideal = query(admin_client, source="ideal", strategy_id=s["id"])
    assert ideal["backtest"] is None
    assert ideal["ideal"]["kpis"]["trades"] == ideal["counts"]["ideal"] > 0
    assert set(ideal["ideal"]["distributions"]) == {"tp_r", "sl_distance", "tp_distance", "duration"}
    cmp = query(admin_client, source="compare", strategy_id=s["id"])
    assert cmp["ideal"] and cmp["backtest"] and cmp["compare"]
    c = cmp["compare"]
    assert c["ideal_n"] == ideal["counts"]["ideal"] and c["backtest_n"] == 10
    assert c["capture_winners"] == pytest.approx(c["backtest_avg_win_r"] / c["ideal_avg_r"], abs=1e-3)


def test_reconcile_is_ok_after_import_and_flags_a_deleted_trade(admin_client):
    s = new_strategy(admin_client)
    result = do_import(admin_client, s["id"], "backtest")
    rec = query(admin_client, strategy_id=s["id"])["reconcile"]
    assert len(rec) == 1 and rec[0]["ok"] is True
    assert rec[0]["csv"]["trades"] == rec[0]["app"]["trades"] == 10
    assert rec[0]["csv"]["rpnl_sum"] == rec[0]["app"]["pnl"]
    admin_client.delete(f"/api/trades/{result['trades'][0]['id']}")
    rec = query(admin_client, strategy_id=s["id"])["reconcile"][0]
    assert rec["ok"] is False and rec["diff_trades"] == -1
    assert any("since deleted" in n for n in rec["notes"])


def test_reconcile_explains_winners_only_ideal_import(admin_client):
    s = new_strategy(admin_client)
    do_import(admin_client, s["id"], "ideal")
    rec = query(admin_client, source="ideal", strategy_id=s["id"])["reconcile"][0]
    assert rec["ok"] is True
    assert rec["csv"]["trades"] == 10 and rec["kept"]["trades"] < 10
    assert "not winners" in rec["notes"][0]


@pytest.mark.skipif(not REAL_SAMPLE.exists(), reason="Jamie's real CSV isn't on this machine")
def test_real_sample_reconciles(admin_client):
    s = new_strategy(admin_client)
    do_import(admin_client, s["id"], "backtest", data=REAL_SAMPLE.read_bytes())
    out = query(admin_client, strategy_id=s["id"])
    rec = out["reconcile"][0]
    assert rec["ok"] is True and rec["balance_ok"] is True
    assert rec["csv"]["trades"] == 8 and rec["csv"]["rpnl_sum"] == pytest.approx(5475.76)
    assert out["backtest"]["kpis"]["net_pnl"] == pytest.approx(5475.76)


def test_filters_narrow_the_rows(db, admin, admin_client):
    s = seeded(db, admin, 120)
    every = query(admin_client, strategy_id=s.id)
    assert every["counts"]["filtered"] == 120

    def n(**filters):
        return query(admin_client, strategy_id=s.id, filters=filters)["counts"]["filtered"]

    mondays = n(weekdays=[0])
    assert 0 < mondays < 120
    assert n(weekdays=[0, 1]) > mondays
    longs, shorts = n(directions=["buy"]), n(directions=["sell"])
    assert longs + shorts == 120
    assert n(entry_models=["FVG"]) + n(entry_models=["Breaker", "OTE", "Order block"]) == 120
    assert n(sessions=["London"]) < 120
    wins = n(outcomes=["win"])
    assert wins == every["backtest"]["kpis"]["wins"]
    assert n(outcomes=["win", "loss", "breakeven"]) == 120
    kept, broken = n(rules="all_kept"), n(rules="any_broken")
    assert kept + broken == 120 and broken > 0
    assert n(date_from="2025-04-01", date_to="2025-04-30") < 120
    assert n(instruments=["nas100"]) == 120 and n(instruments=["EURUSD"]) == 0
    assert n(owners=[admin.id]) == 120


def test_entry_time_window_wraps_midnight(db, admin, admin_client):
    s = seeded(db, admin, 150)
    out = query(admin_client, strategy_id=s.id, filters={"time_from": "22:00", "time_to": "06:00"})
    hours = {int(t["opened_at"][11:13]) for t in out["trades"]}
    assert out["counts"]["filtered"] > 0
    assert hours <= {21, 22, 23, 0, 1, 2, 3, 4, 5, 6}  # UTC hours; UK is GMT or BST
    day = query(admin_client, strategy_id=s.id, filters={"time_from": "08:00", "time_to": "13:00"})
    assert day["counts"]["filtered"] + out["counts"]["filtered"] < 150


def test_tag_filter_is_synonym_aware(admin_client):
    s = new_strategy(admin_client)
    t = admin_client.post(
        f"/api/strategies/{s['id']}/trades",
        json={"kind": "backtest", "instrument": "NAS100", "side": "buy", "opened_at": "2026-03-03T10:00:00Z",
              "r_multiple": 2.0, "pnl": 200, "tags": ["Fair value gap"]},
    )  # fmt: skip
    assert t.status_code == 201, t.text
    admin_client.post(
        f"/api/strategies/{s['id']}/trades",
        json={"kind": "backtest", "instrument": "NAS100", "side": "sell", "opened_at": "2026-03-04T10:00:00Z",
              "r_multiple": -1.0, "pnl": -100},
    )  # fmt: skip
    for name in ("FVG", "f.v.g", "fair value gap"):
        assert query(admin_client, strategy_id=s["id"], filters={"tags": [name]})["counts"]["filtered"] == 1
    out = query(admin_client, strategy_id=s["id"], filters={"tags": ["no such tag"]})
    assert out["counts"]["filtered"] == 0 and out["notes"]["unresolved_tags"] == ["no such tag"]


def test_news_filter_without_news_data_keeps_only_no_data_trades(db, admin, admin_client):
    # Prompt 4 made the News filter live (it used to be ignored while there was no news data).
    s = seeded(db, admin, 20)
    out = query(admin_client, strategy_id=s.id, filters={"news": "inside"})
    assert out["counts"]["filtered"] == 0 and out["news_status"] == "no_data"
    out = query(admin_client, strategy_id=s.id, filters={"news": "no_data"})
    assert out["counts"]["filtered"] == 20


def test_bad_filters_are_422(admin_client):
    res = admin_client.post("/api/analytics/query", json={"filters": {"time_from": "25:00"}})
    assert res.status_code == 422
    res = admin_client.post("/api/analytics/query", json={"filters": {"weekdays": [7]}})
    assert res.status_code == 422
    res = admin_client.post("/api/analytics/query", json={"source": "everything"})
    assert res.status_code == 422


def test_scope_and_split_by_owner(db, admin, member, admin_client, member_client):
    seeded(db, admin, 30, name="Jamie's", seed=1)
    seeded(db, member, 20, name="Sam's", seed=2)
    assert query(member_client, scope="everyone")["counts"]["filtered"] == 50
    assert query(member_client, scope="mine")["counts"]["filtered"] == 20
    assert query(member_client, scope="others")["counts"]["filtered"] == 30
    split = query(admin_client, split_by_owner=True)
    owners = {o["owner"]["display_name"]: o for o in split["owners"]}
    assert set(owners) == {"Jamie", "Sam"}
    assert owners["Sam"]["kpis"]["trades"] == 20 and len(owners["Sam"]["equity"]) == 20
    assert "colour_index" in owners["Jamie"]["owner"]
    assert {o["display_name"] for o in split["options"]["owners"]} == {"Jamie", "Sam"}


def test_members_can_read_everyones_analytics_but_must_sign_in(db, admin, member_client, client):
    s = seeded(db, admin, 10)
    assert query(member_client, strategy_id=s.id)["counts"]["filtered"] == 10
    assert client.post("/api/analytics/query", json={}).status_code == 401
    assert member_client.post("/api/analytics/query", json={"strategy_id": 99999}).status_code == 404


def test_deleted_strategies_and_trades_are_left_out(db, admin, admin_client):
    s = seeded(db, admin, 10)
    s.deleted_at = datetime.now(UTC)
    db.commit()
    assert query(admin_client)["counts"]["filtered"] == 0


def test_breakeven_threshold_comes_from_the_viewer(db, admin, admin_client):
    s = seeded(db, admin, 60)
    before = query(admin_client, strategy_id=s.id)["backtest"]["kpis"]
    admin_client.patch("/api/me", json={"breakeven_threshold": 50})
    after = query(admin_client, strategy_id=s.id)
    assert after["breakeven_threshold"] == 50
    assert after["backtest"]["kpis"]["breakevens"] > before["breakevens"]


def test_insights_come_with_the_query(db, admin, admin_client):
    s = seeded(db, admin, 200)
    out = query(admin_client, strategy_id=s.id)
    assert len(out["insights"]) <= 3
    for i in out["insights"]:
        assert i["n"] >= 8 and ("early signal" in i["text"]) == (i["n"] < 20)


def test_five_thousand_trades_come_back_fast(db, admin, admin_client):
    """Budget: under 300 ms locally. Checked loosely here (CI machines vary)."""
    s = seeded(db, admin, 5000)
    query(admin_client, strategy_id=s.id)  # warm up
    started = time.perf_counter()
    out = query(admin_client, strategy_id=s.id)
    elapsed = time.perf_counter() - started
    assert out["counts"]["filtered"] == 5000
    print(f"\n5,000-trade analytics query: {elapsed * 1000:.0f} ms")
    assert elapsed < 1.0


def test_session_insights_for_the_recap(db, admin, admin_client):
    s = new_strategy(admin_client)
    result = do_import(admin_client, s["id"], "backtest")
    out = admin_client.get(f"/api/journal/sessions/{result['session']['id']}/insights")
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["session_trades"] == 10 and body["min_slice"] == 8
    assert isinstance(body["top"], list)
    assert (
        body["session_vs_baseline"] is None
    )  # the session is the whole strategy: nothing to compare against
    assert admin_client.get("/api/journal/sessions/99999/insights").status_code == 404


def test_non_finite_numbers_never_reach_the_analytics(admin_client):
    """An 'inf' in a CSV or an Infinity in JSON is refused; histograms cope with odd stored values anyway."""
    from app.services.analytics.series import histogram
    from app.services.fxreplay import parse_csv

    bad = SAMPLE.replace(b",250.0,", b",inf,", 1)
    result = parse_csv(bad)
    assert any("not a finite number" in p for p in result.problems)
    s = new_strategy(admin_client)
    res = admin_client.post(
        f"/api/strategies/{s['id']}/trades",
        content=b'{"kind":"backtest","instrument":"NAS100","side":"buy","opened_at":"2026-03-03T10:00:00Z",'
        b'"r_multiple":Infinity}',
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 422
    assert histogram([float("inf"), float("nan")], 0.5) == []
    bins = histogram([0.0, 1e300], 0.5)
    assert len(bins) <= 40 and sum(b["n"] for b in bins) == 2


def test_insights_compare_with_the_unfiltered_baseline(db, admin, admin_client):
    s = seeded(db, admin, 200)
    plain = query(admin_client, strategy_id=s.id)["insights"]
    filtered = query(admin_client, strategy_id=s.id, filters={"weekdays": [0]})["insights"]
    assert plain == filtered
