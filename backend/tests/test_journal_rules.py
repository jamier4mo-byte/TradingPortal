"""Coverage and unlock (F9): one function, one set of constants."""

from datetime import UTC, datetime

from app.services import journal_rules as rules


def dt(y, m, d, h=10):
    return datetime(y, m, d, h, tzinfo=UTC)


def test_constants_are_the_rule():
    assert rules.COVERAGE_MONTHS == 6
    assert rules.MIN_UNLOCK_TRADES == 6
    assert rules.DEFAULT_BREAKEVEN_THRESHOLD == 2.0


def test_empty():
    cov = rules.coverage([])
    assert cov.months == [] and not cov.unlocked and cov.progress == 0


def test_exactly_six_consecutive_months_unlocks():
    cov = rules.coverage([dt(2026, m, 15) for m in range(1, 7)])
    assert cov.covered_count == 6 and cov.best_run == 6 and cov.unlocked
    assert cov.progress == 1.0 and cov.next_uncovered is None
    five = rules.coverage([dt(2026, m, 15) for m in range(1, 6)])
    assert not five.unlocked and five.best_run == 5 and five.next_uncovered == "2026-06"


def test_a_gap_month_breaks_the_run():
    cov = rules.coverage([dt(2026, m, 15) for m in (1, 2, 3, 5, 6, 7, 8)])
    assert [mo["month"] for mo in cov.months] == [f"2026-0{m}" for m in range(1, 9)]
    assert cov.months[3] == {"month": "2026-04", "trades": 0, "covered": False}
    assert cov.covered_count == 7 and cov.best_run == 4 and not cov.unlocked
    assert cov.next_uncovered == "2026-04"


def test_year_boundary_counts_as_consecutive():
    cov = rules.coverage(
        [dt(2025, 10, 1), dt(2025, 11, 1), dt(2025, 12, 31), dt(2026, 1, 1), dt(2026, 2, 1), dt(2026, 3, 1)]
    )
    assert cov.first_month == "2025-10" and cov.last_month == "2026-03"
    assert cov.best_run == 6 and cov.unlocked


def test_trade_near_midnight_uses_uk_date_not_utc():
    # 23:30 UTC on 30 June is 00:30 BST on 1 July: it covers July, not June.
    cov = rules.coverage([datetime(2026, 6, 30, 23, 30, tzinfo=UTC)])
    assert cov.months == [{"month": "2026-07", "trades": 1, "covered": True}]
    # In January (GMT) the same clock time stays on the same day.
    cov = rules.coverage([datetime(2026, 1, 31, 23, 30, tzinfo=UTC)])
    assert cov.months[0]["month"] == "2026-01"


def test_six_months_but_too_few_trades_is_impossible_by_construction():
    # One trade per month is six trades: the minimum. Many trades in one month don't help the run.
    cov = rules.coverage([dt(2026, 1, d) for d in range(1, 20)])
    assert cov.trade_count == 19 and cov.best_run == 1 and not cov.unlocked


def test_stage():
    locked = rules.coverage([dt(2026, 1, 1)])
    unlocked = rules.coverage([dt(2026, m, 1) for m in range(1, 7)])
    assert rules.stage(locked, 0) == "ideal"
    assert rules.stage(unlocked, 0) == "ready"
    assert rules.stage(unlocked, 3) == "backtesting"


def test_session_windows_in_uk_time():
    assert rules.session_label(datetime(2026, 7, 1, 6, 0, tzinfo=UTC)) == "Asia"  # 07:00 BST
    assert rules.session_label(datetime(2026, 7, 1, 7, 0, tzinfo=UTC)) == "London"  # 08:00 BST
    assert rules.session_label(datetime(2026, 7, 1, 12, 0, tzinfo=UTC)) == "New York"  # 13:00 BST
    assert rules.session_label(datetime(2026, 7, 1, 21, 30, tzinfo=UTC)) == "Out of session"  # 22:30 BST
    assert rules.session_label(datetime(2026, 1, 1, 8, 0, tzinfo=UTC)) == "London"  # GMT
