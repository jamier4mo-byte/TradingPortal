"""Every metric against numbers worked out by hand (F16).

The main fixture, six trades booked in this order (breakeven threshold $2):

    #  R      P&L    outcome    held     rules            MFE   MAE
    1  +2.00  +200   win        1h       r1 ✓ r2 ✓        4.0   −0.4
    2  −1.00  −100   loss       30m      r1 ✓ r2 ✗        0.5
    3  +0.01  +1     breakeven  10m      –
    4  +3.00  +300   win        2h       r1 ✓ r2 ✓        3.0   −0.2
    5  −1.00  −100   loss       30m      r1 ✗ r2 ✓
    6  −1.00  −100   loss       –        –

Worked out:
- wins 2, losses 3, breakevens 1 → win rate 2 / 5 = 0.4 (breakeven left out)
- net P&L 201; total R 2.01; average R 2.01 / 6 = 0.335
- average win 2.5R / $250; average loss −1R / −$100
- expectancy 0.4 × 2.5 − 0.6 × 1 = 0.4R; 0.4 × 250 − 0.6 × 100 = $40
- profit factor 500 / 300 = 1.6667 (R: 5 / 3)
- cumulative R 2, 1, 1.01, 4.01, 3.01, 2.01 → peak 4.01, trough 2.01 → max drawdown −2.0R (P&L −200)
- outcomes W L B W L L → longest win streak 1, longest loss streak 2
- durations 3600, 1800, 600, 7200, 1800 → mean 3000; wins 5400; losses 1800
- rules: 4 marked, 2 all kept → 0.5
- exit efficiency (2 + 0 + 3) / (4 + 0.5 + 3) = 0.6667; R left mean(2, 1.5, 0) = 1.1667
- winner drawdown mean(0.4, 0.2) = 0.3
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.analytics import series
from app.services.analytics.insights import insights
from app.services.analytics.metrics import REGISTRY, compute, max_drawdown, registry_meta, streaks
from app.services.analytics.rows import Row, classify, prepare

T0 = datetime(2026, 3, 2, 9, 0, tzinfo=UTC)  # Monday 09:00 UK (GMT)


def row(i: int, r: float | None, pnl: float | None, *, held: int | None = 3600, **kw) -> Row:
    opened = kw.pop("opened_at", T0 + timedelta(days=i))
    closed = opened + timedelta(seconds=held) if held is not None else None
    return Row(id=i, kind=kw.pop("kind", "backtest"), opened_at=opened, closed_at=closed, r=r, pnl=pnl,
               duration_seconds=held, **kw)  # fmt: skip


@pytest.fixture
def mixed() -> list[Row]:
    return prepare(
        [
            row(1, 2.0, 200, held=3600, rules={"r1": True, "r2": True}, mfe_r=4.0, mae_r=-0.4),
            row(2, -1.0, -100, held=1800, rules={"r1": True, "r2": False}, mfe_r=0.5),
            row(3, 0.01, 1.0, held=600),
            row(4, 3.0, 300, held=7200, rules={"r1": True, "r2": True}, mfe_r=3.0, mae_r=-0.2),
            row(5, -1.0, -100, held=1800, rules={"r1": False, "r2": True}),
            row(6, -1.0, -100, held=None),
        ]
    )


def test_mixed_fixture_matches_hand_computed(mixed):
    k = compute(mixed)
    assert k["trades"] == 6
    assert (k["wins"], k["losses"], k["breakevens"]) == (2, 3, 1)
    assert k["win_rate"] == pytest.approx(0.4)
    assert k["net_pnl"] == pytest.approx(201)
    assert k["total_r"] == pytest.approx(2.01)
    assert k["avg_r"] == pytest.approx(0.335)
    assert k["avg_win_r"] == pytest.approx(2.5)
    assert k["avg_loss_r"] == pytest.approx(-1.0)
    assert k["avg_win_pnl"] == pytest.approx(250)
    assert k["avg_loss_pnl"] == pytest.approx(-100)
    assert k["expectancy_r"] == pytest.approx(0.4)
    assert k["expectancy_pnl"] == pytest.approx(40)
    assert k["profit_factor"] == pytest.approx(1.6667, abs=1e-4)
    assert k["profit_factor_r"] == pytest.approx(1.6667, abs=1e-4)
    assert k["max_dd_r"] == pytest.approx(-2.0)
    assert k["max_dd_pnl"] == pytest.approx(-200)
    assert k["longest_win_streak"] == 1
    assert k["longest_loss_streak"] == 2
    assert k["best_r"] == 3.0 and k["worst_r"] == -1.0
    assert k["best_pnl"] == 300 and k["worst_pnl"] == -100
    assert k["max_win_r"] == 3.0
    assert k["avg_duration"] == pytest.approx(3000)
    assert k["avg_win_duration"] == pytest.approx(5400)
    assert k["avg_loss_duration"] == pytest.approx(1800)
    assert k["rules_kept_rate"] == pytest.approx(0.5)
    assert k["exit_efficiency"] == pytest.approx(0.6667, abs=1e-4)
    assert k["r_left_on_table"] == pytest.approx(1.1667, abs=1e-4)
    assert k["avg_winner_mae"] == pytest.approx(0.3)


def test_all_wins():
    rows = prepare([row(i, float(i), 100.0 * i) for i in (1, 2, 3)])
    k = compute(rows)
    assert k["win_rate"] == 1.0
    assert k["profit_factor"] is None  # no losses: undefined, never infinite
    assert k["profit_factor_r"] is None
    assert k["max_dd_r"] == 0 and k["max_dd_pnl"] == 0
    assert k["expectancy_r"] == pytest.approx(2.0)
    assert k["avg_loss_r"] is None
    assert k["longest_win_streak"] == 3 and k["longest_loss_streak"] == 0
    assert k["total_r"] == 6.0 and k["net_pnl"] == 600


def test_all_losses():
    rows = prepare([row(i, -1.0, -100.0) for i in (1, 2, 3)])
    k = compute(rows)
    assert k["win_rate"] == 0.0
    assert k["profit_factor"] == 0.0
    assert k["expectancy_r"] == pytest.approx(-1.0)
    assert k["expectancy_pnl"] == pytest.approx(-100)
    assert k["max_dd_r"] == pytest.approx(-3.0)
    assert k["max_dd_pnl"] == pytest.approx(-300)
    assert k["longest_loss_streak"] == 3 and k["longest_win_streak"] == 0
    assert k["avg_win_r"] is None and k["best_r"] == -1.0


def test_breakeven_heavy():
    # B B W B B L B: win rate 1 / 2; breakevens break streaks; expectancy 0.5 × 2 − 0.5 × 1 = 0.5
    rows = prepare(
        [
            row(1, 0.0, 0.0),
            row(2, 0.01, 1.5),
            row(3, 2.0, 200.0),
            row(4, -0.01, -2.0),  # exactly −threshold is still breakeven
            row(5, 0.02, 2.0),  # exactly +threshold is still breakeven
            row(6, -1.0, -100.0),
            row(7, 0.0, -0.5),
        ]
    )
    k = compute(rows)
    assert (k["wins"], k["losses"], k["breakevens"]) == (1, 1, 5)
    assert k["win_rate"] == pytest.approx(0.5)
    assert k["expectancy_r"] == pytest.approx(0.5)
    assert k["avg_r"] == pytest.approx((2.0 - 1.0 + 0.01 - 0.01 + 0.02) / 7, abs=1e-4)
    assert k["longest_win_streak"] == 1 and k["longest_loss_streak"] == 1
    assert k["profit_factor"] == pytest.approx(2.0)


def test_only_breakevens_have_no_win_rate():
    k = compute(prepare([row(1, 0.0, 0.0), row(2, 0.0, 1.0)]))
    assert k["win_rate"] is None
    assert k["expectancy_r"] is None
    assert k["profit_factor"] is None


def test_single_trade():
    k = compute(prepare([row(1, 1.5, 150.0, held=5400)]))
    assert k["trades"] == 1
    assert k["win_rate"] == 1.0
    assert k["total_r"] == 1.5 and k["avg_r"] == 1.5
    assert k["max_dd_r"] == 0
    assert k["longest_win_streak"] == 1
    assert k["avg_duration"] == 5400
    assert k["best_r"] == k["worst_r"] == 1.5


def test_no_trades_gives_nothing_not_zero():
    k = compute([])
    assert k["trades"] == 0
    for key in (
        "win_rate",
        "net_pnl",
        "total_r",
        "avg_r",
        "expectancy_r",
        "profit_factor",
        "max_dd_r",
        "best_r",
    ):
        assert k[key] is None, key
    assert k["longest_win_streak"] is None


def test_threshold_is_inclusive_and_configurable():
    r = row(1, 0.02, 2.0)
    assert classify(r, 2.0) == "breakeven"
    r.pnl = 2.01
    assert classify(r, 2.0) == "win"
    assert classify(row(2, 0.0, 0.5), 0.0) == "win"
    assert classify(row(3, -0.5, None), 2.0) == "loss"  # no P&L: falls back to the sign of R


def test_pnl_is_booked_at_close():
    # Opened first but closed last: it is the last point on the equity curve.
    a = row(1, -1.0, -100.0, held=10 * 86400)
    b = row(2, 2.0, 200.0, held=3600)
    rows = prepare([a, b])
    assert [r.id for r in rows] == [2, 1]
    assert compute(rows)["max_dd_r"] == pytest.approx(-1.0)


def test_helpers():
    assert max_drawdown([1, -2, 3, -1, -1]) == -2
    assert max_drawdown([-1, -1]) == -2  # the curve starts at 0, so an opening loss is a drawdown
    assert streaks(["win", "win", "breakeven", "win", "loss", "loss", None, "loss"]) == {
        "win": [2, 1],
        "loss": [2, 1],
    }


def test_registry_has_formula_text_for_every_metric():
    ids = [m.id for m in REGISTRY]
    assert len(ids) == len(set(ids))
    for m in registry_meta():
        assert m["label"] and m["formula"] and m["unit"] in ("count", "pct", "r", "usd", "duration", "ratio")
    win = next(m for m in registry_meta() if m["id"] == "win_rate")
    assert "Breakevens are left out" in win["formula"]
    assert {"trades", "avg_r", "avg_tp_r", "median_duration"} <= set(compute([], "ideal"))
    assert "win_rate" not in compute([], "ideal")


# ---- series ------------------------------------------------------------------------------------


def test_breakdowns_and_calendar(mixed):
    b = series.breakdowns(mixed)
    weekday = {g["key"]: g for g in b["weekday"]}
    # T0 is Monday 2 Mar; trades 1..6 fall Tue..Sun (day offsets 1..6)
    assert weekday["Tue"]["n"] == 1 and weekday["Tue"]["total_r"] == 2.0
    assert weekday["Mon"]["n"] == 0
    assert [g["key"] for g in b["weekday"]][:5] == ["Mon", "Tue", "Wed", "Thu", "Fri"]
    assert {g["key"] for g in b["direction"]} == {"Long"}
    assert b["hour"][0]["key"] == "09:00" and b["hour"][0]["n"] == 6
    cal = series.calendar(mixed + prepare([row(7, 1.0, 100.0, opened_at=T0 + timedelta(days=1, hours=2))]))
    tue = next(d for d in cal if d["date"] == "2026-03-03")
    assert tue["n"] == 2 and tue["pnl"] == 300 and tue["r"] == 3.0


def test_equity_and_drawdown_series(mixed):
    eq = series.equity(mixed)
    assert [p["cum_r"] for p in eq] == [2.0, 1.0, 1.01, 4.01, 3.01, 2.01]
    assert [p["dd_r"] for p in eq] == [0.0, -1.0, -0.99, 0.0, -1.0, -2.0]
    runs = series.streak_runs(mixed)
    assert [(s["outcome"], s["length"]) for s in runs] == [
        ("win", 1),
        ("loss", 1),
        ("breakeven", 1),
        ("win", 1),
        ("loss", 2),
    ]


def test_r_distribution_bins():
    rows = prepare([row(1, -1.0, -100), row(2, -0.9, -90), row(3, 2.2, 220), row(4, 0.0, 0)])
    bins = series.r_distribution(rows)
    assert bins[0] == {"from": -1.0, "to": -0.5, "n": 2}
    assert sum(b["n"] for b in bins) == 4
    assert bins[-1]["from"] == 2.0


def test_rulebook_costs(mixed):
    rb = series.rulebook(mixed, [{"key": "r1", "text": "Bias"}, {"key": "r2", "text": "Killzone"}])
    assert rb["marked"] == 4
    assert rb["all_kept"]["n"] == 2 and rb["all_kept"]["total_r"] == 5.0
    assert rb["any_broken"]["n"] == 2 and rb["any_broken"]["total_r"] == -2.0
    r1 = rb["rules"][0]
    assert r1["text"] == "Bias" and r1["kept"] == 3 and r1["broken"] == 1
    assert r1["avg_r_kept"] == pytest.approx(4 / 3, abs=1e-4)
    assert r1["cost_r"] == pytest.approx(1 * (4 / 3 + 1), abs=1e-4)


def test_compare_capture():
    ideal = prepare([row(i, 4.0, 400.0, kind="ideal") for i in (1, 2)])
    bt = prepare([row(3, 2.0, 200.0), row(4, 3.0, 300.0), row(5, -1.0, -100.0)])
    c = series.compare(ideal, bt)
    assert c["ideal_avg_r"] == 4.0
    assert c["backtest_avg_win_r"] == 2.5
    assert c["capture_winners"] == pytest.approx(0.625)
    assert c["capture_all"] == pytest.approx((4 / 3) / 4, abs=1e-4)
    hours = {h["key"]: h for h in c["by_hour"]}
    assert hours["09:00"]["ideal_n"] == 2 and hours["09:00"]["backtest_n"] == 3
    assert hours["09:00"]["holds"] == "holds"


# ---- insights (U11) ----------------------------------------------------------------------------


def _insight_rows(mondays: int, others: int = 21) -> list[Row]:
    rows = []
    monday = datetime(2026, 3, 2, 9, 0, tzinfo=UTC)
    tuesday = monday + timedelta(days=1)
    for i in range(mondays):
        rows.append(row(i, 2.0, 200, kind="ideal", opened_at=monday + timedelta(weeks=i), sl_distance=6.0))
    for i in range(others):
        rows.append(
            row(100 + i, 2.0, 200, kind="ideal", opened_at=tuesday + timedelta(weeks=i), sl_distance=10.0)
        )
    return prepare(rows)


def test_insight_reports_the_slice_difference_and_early_signal():
    # baseline SL = (9 × 6 + 21 × 10) / 30 = 8.8; Mondays 6 → (6 − 8.8) / 8.8 = −31.8% → "32% tighter"
    found = insights(_insight_rows(9), "ideal")
    assert found[0]["text"] == "Mondays: SL 32% tighter, n=9 · early signal"
    assert found[0]["early"] is True
    assert all("Tuesdays" not in f["text"] for f in found)  # +13.6% is under the 15% bar


def test_insight_needs_eight_trades_per_slice():
    assert insights(_insight_rows(7), "ideal") == []


def test_insight_without_early_label_from_twenty():
    found = insights(_insight_rows(20, 40), "ideal")
    assert found[0]["text"].startswith("Mondays: SL ")
    assert "early signal" not in found[0]["text"]
