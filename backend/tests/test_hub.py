"""GET /api/hub: welcome back, the process streak, personal bests, the first-run checklist and the week recap.

The clock is frozen through `app.api.hub.utcnow`, and trades are hand-built so every number is known.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.api import hub as hub_api
from app.models import AppState, JournalSession, PushSubscription, Strategy, Trade
from app.services import hub as hub_svc
from tests.test_journal_api import do_import, new_strategy

FRI_NOON = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)  # Friday 6 Nov 2026, 12:00 UK (GMT)


@pytest.fixture
def frozen(monkeypatch):
    def set_now(now: datetime) -> None:
        monkeypatch.setattr(hub_api, "utcnow", lambda: now)

    set_now(FRI_NOON)
    return set_now


def get(client):
    res = client.get("/api/hub")
    assert res.status_code == 200, res.text
    return res.json()


def strategy(db, user, name="Hand-built") -> Strategy:
    s = Strategy(owner_id=user.id, name=name, instruments=["NAS100"])
    db.add(s)
    db.commit()
    return s


def trade(
    db,
    user,
    strat: Strategy,
    opened: datetime,
    *,
    r: float | None = None,
    pnl: float | None = None,
    rules: dict | None = None,
    kind: str = "backtest",
    created: datetime | None = None,
    annotated: datetime | None = None,
    closed: datetime | None = None,
) -> Trade:
    t = Trade(
        owner_id=user.id,
        strategy_id=strat.id,
        kind=kind,
        instrument="NAS100",
        side="buy",
        opened_at=opened,
        closed_at=closed or opened + timedelta(hours=1),
        market_date=hub_svc._uk_date(opened),
        r_multiple=r,
        pnl=pnl,
        rules_followed=rules or {},
        created_at=created or opened,
        updated_at=created or opened,
        annotated_at=annotated,
    )
    db.add(t)
    db.commit()
    return t


def session(db, user, strat: Strategy, created: datetime, note: str = "", updated: datetime | None = None):
    s = JournalSession(
        owner_id=user.id,
        strategy_id=strat.id,
        kind="backtest",
        csv_timezone="Europe/London",
        created_at=created,
        updated_at=updated or created,
        improve_note=note,
    )
    db.add(s)
    db.commit()
    return s


# ---- auth and shape --------------------------------------------------------------------------


def test_hub_needs_a_signed_in_user(client):
    assert client.get("/api/hub").status_code == 401


def test_shape_for_a_brand_new_account(admin_client, frozen):
    out = get(admin_client)
    assert set(out) == {"welcome_back", "server_now", "streak", "personal_bests", "checklist", "week_recap"}
    assert out["server_now"] == "2026-11-06T12:00:00Z"
    assert out["personal_bests"] == []
    assert out["streak"]["current_days"] == 0 and out["streak"]["best_days"] == 0
    assert out["streak"]["last_active_date"] is None and out["streak"]["active_today"] is False
    assert len(out["streak"]["days"]) == 28 and out["streak"]["days"][-1] == {
        "date": "2026-11-06",
        "active": False,
    }
    assert out["checklist"] == {
        "twelve_data_key": False,
        "strategy_created": False,
        "first_csv_imported": False,
        "alerts_enabled": False,
        "all_done_server": False,
    }


# ---- welcome back ----------------------------------------------------------------------------


def test_first_visit_by_a_fresh_account_is_not_a_welcome_back(admin_client, frozen, db, admin):
    frozen(datetime.now(UTC))
    assert get(admin_client)["welcome_back"] is False
    assert db.get(AppState, f"hub_visit:{admin.id}") is not None


def test_first_visit_by_an_older_account_is_a_welcome_back(admin_client, frozen, db, admin):
    admin.created_at = FRI_NOON - timedelta(days=3)
    db.commit()
    assert get(admin_client)["welcome_back"] is True


def test_welcome_back_within_24h_is_off_and_after_25h_on(admin_client, frozen, db, admin):
    admin.created_at = FRI_NOON - timedelta(days=3)
    db.commit()
    get(admin_client)  # records the visit
    frozen(FRI_NOON + timedelta(hours=23))
    assert get(admin_client)["welcome_back"] is False
    frozen(FRI_NOON + timedelta(hours=23 + 25))
    assert get(admin_client)["welcome_back"] is True
    # and the visit was moved on, so the next call inside 24 h is quiet again
    frozen(FRI_NOON + timedelta(hours=23 + 25 + 1))
    assert get(admin_client)["welcome_back"] is False


def test_visits_are_per_user(admin_client, member_client, frozen, db, admin, member):
    admin.created_at = member.created_at = FRI_NOON - timedelta(days=3)
    db.commit()
    assert get(admin_client)["welcome_back"] is True
    assert get(member_client)["welcome_back"] is True
    assert get(admin_client)["welcome_back"] is False


# ---- streak ----------------------------------------------------------------------------------


def test_streak_counts_sessions_notes_logs_and_annotations(admin_client, frozen, db, admin):
    s = strategy(db, admin)
    session(db, admin, s, datetime(2026, 11, 4, 9, 0, tzinfo=UTC))  # Wed: session created
    # Thu: a session from October whose improve note was written on Thursday
    session(db, admin, s, datetime(2026, 10, 20, 9, 0, tzinfo=UTC), "Wait for the FVG",
            updated=datetime(2026, 11, 5, 20, 0, tzinfo=UTC))  # fmt: skip
    # Oct 21 and 22: an ideal trade logged, and a trade annotated (so Oct 20–22 is a 3-day run)
    trade(db, admin, s, datetime(2026, 10, 21, 9, 0, tzinfo=UTC), kind="ideal", r=1.0)
    trade(
        db,
        admin,
        s,
        datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        annotated=datetime(2026, 10, 22, 9, 0, tzinfo=UTC),
    )
    # A missed setup is not "showing up" on its own
    trade(db, admin, s, datetime(2026, 11, 2, 9, 0, tzinfo=UTC), kind="missed")
    out = get(admin_client)["streak"]
    assert out["active_today"] is False  # nothing yet on Friday: the streak is still alive
    assert out["current_days"] == 2 and out["best_days"] == 3
    assert out["last_active_date"] == "2026-11-05"
    active = [d["date"] for d in out["days"] if d["active"]]
    assert active == ["2026-10-20", "2026-10-21", "2026-10-22", "2026-11-04", "2026-11-05"]


def test_streak_uses_uk_dates_across_midnight(admin_client, frozen, db, admin):
    s = strategy(db, admin)
    # 23:30 UTC on 14 July is 00:30 BST on 15 July
    trade(db, admin, s, datetime(2026, 7, 14, 23, 30, tzinfo=UTC), r=1.0)
    frozen(datetime(2026, 7, 15, 10, 0, tzinfo=UTC))
    out = get(admin_client)["streak"]
    assert out["active_today"] is True and out["current_days"] == 1
    assert out["last_active_date"] == "2026-07-15"


def test_streak_breaks_when_yesterday_was_missed(admin_client, frozen, db, admin):
    s = strategy(db, admin)
    session(db, admin, s, datetime(2026, 11, 3, 9, 0, tzinfo=UTC))
    session(db, admin, s, datetime(2026, 11, 4, 9, 0, tzinfo=UTC))
    out = get(admin_client)["streak"]  # Friday; Thursday had nothing
    assert out["current_days"] == 0 and out["best_days"] == 2


def test_streak_is_the_users_own(admin_client, member_client, frozen, db, member):
    s = strategy(db, member)
    session(db, member, s, datetime(2026, 11, 5, 9, 0, tzinfo=UTC))
    assert get(member_client)["streak"]["current_days"] == 1
    assert get(admin_client)["streak"]["current_days"] == 0


# ---- personal bests --------------------------------------------------------------------------


def test_best_month_in_r(admin_client, frozen, db, admin):
    s = strategy(db, admin)
    recent = FRI_NOON - timedelta(days=2)
    trade(db, admin, s, datetime(2026, 3, 3, 9, 0, tzinfo=UTC), r=2.0, created=recent)
    trade(db, admin, s, datetime(2026, 3, 10, 9, 0, tzinfo=UTC), r=3.0, created=recent)
    trade(db, admin, s, datetime(2026, 4, 7, 9, 0, tzinfo=UTC), r=1.0, created=recent)
    trade(db, admin, s, datetime(2026, 4, 8, 9, 0, tzinfo=UTC), r=-2.0, created=recent)
    bests = {b["key"]: b for b in get(admin_client)["personal_bests"]}
    assert set(bests) == {"best_month_r"}
    best = bests["best_month_r"]
    assert best["value"] == 5.0 and best["value_text"] == "+5.0 R" and best["detail"] == "March 2026"
    assert best["achieved_at"] == "2026-11-04T12:00:00Z" and best["is_new"] is True


def test_best_month_is_not_new_after_a_week_and_ignores_ideal_trades(admin_client, frozen, db, admin):
    s = strategy(db, admin)
    old = FRI_NOON - timedelta(days=30)
    trade(db, admin, s, datetime(2026, 3, 3, 9, 0, tzinfo=UTC), r=2.0, created=old)
    trade(db, admin, s, datetime(2026, 5, 3, 9, 0, tzinfo=UTC), r=9.0, created=old, kind="ideal")
    [best] = get(admin_client)["personal_bests"]
    assert best["key"] == "best_month_r" and best["value"] == 2.0 and best["is_new"] is False


def test_longest_rule_run_skips_unmarked_trades_and_breaks_on_a_broken_rule(admin_client, frozen, db, admin):
    s = strategy(db, admin)
    kept = {"r1": True, "r2": True}
    broken = {"r1": True, "r2": False}
    when = FRI_NOON - timedelta(days=20)
    marks = [kept, kept, kept, {}, kept, broken, kept, kept]
    for i, rules in enumerate(marks):
        trade(db, admin, s, when + timedelta(hours=i), r=1.0, rules=rules, created=when)
    bests = {b["key"]: b for b in get(admin_client)["personal_bests"]}
    run = bests["longest_rule_run"]
    assert run["value"] == 4.0 and run["value_text"] == "4 trades"
    assert run["detail"] == "to 17 Oct 2026" and run["is_new"] is False


def test_rule_run_needs_three_trades_and_is_new_when_annotated_this_week(admin_client, frozen, db, admin):
    s = strategy(db, admin)
    kept = {"r1": True}
    when = FRI_NOON - timedelta(days=20)
    for i in range(2):
        trade(db, admin, s, when + timedelta(hours=i), r=1.0, rules=kept, created=when)
    assert [b["key"] for b in get(admin_client)["personal_bests"]] == ["best_month_r"]
    t = trade(db, admin, s, when + timedelta(hours=2), r=1.0, rules=kept, created=when)
    t.updated_at = FRI_NOON - timedelta(days=1)  # annotated yesterday
    db.commit()
    run = {b["key"]: b for b in get(admin_client)["personal_bests"]}["longest_rule_run"]
    assert run["value"] == 3.0 and run["is_new"] is True


def test_no_trades_means_no_bests(admin_client, frozen, db, admin):
    strategy(db, admin)
    assert get(admin_client)["personal_bests"] == []


# ---- checklist -------------------------------------------------------------------------------


def test_checklist_flags_flip_as_records_appear(admin_client, frozen, db, admin):
    assert admin_client.put("/api/me/keys/twelve_data", json={"key": "abcdefgh1234"}).status_code == 200
    out = get(admin_client)["checklist"]
    assert out["twelve_data_key"] is True and out["strategy_created"] is False
    s = new_strategy(admin_client)
    out = get(admin_client)["checklist"]
    assert out["strategy_created"] is True and out["first_csv_imported"] is False
    do_import(admin_client, s["id"], "ideal")
    out = get(admin_client)["checklist"]
    assert (
        out["first_csv_imported"] is True
        and out["alerts_enabled"] is False
        and out["all_done_server"] is False
    )
    db.add(
        PushSubscription(
            user_id=admin.id, endpoint="https://fcm.googleapis.com/fcm/send/abc", p256dh="p", auth="a"
        )
    )
    db.commit()
    out = get(admin_client)["checklist"]
    assert out["alerts_enabled"] is True and out["all_done_server"] is True


def test_checklist_is_per_user(admin_client, member_client, frozen):
    new_strategy(admin_client)
    assert get(admin_client)["checklist"]["strategy_created"] is True
    assert get(member_client)["checklist"]["strategy_created"] is False


# ---- week recap ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "show", "start"),
    [
        (datetime(2026, 11, 8, 17, 59, tzinfo=UTC), False, "2026-11-02"),  # Sunday 17:59 UK
        (datetime(2026, 11, 8, 18, 0, tzinfo=UTC), True, "2026-11-02"),  # Sunday 18:00 UK
        (datetime(2026, 11, 9, 9, 0, tzinfo=UTC), True, "2026-11-02"),  # Monday
        (datetime(2026, 11, 9, 23, 59, tzinfo=UTC), True, "2026-11-02"),  # Monday 23:59
        (datetime(2026, 11, 10, 0, 0, tzinfo=UTC), False, "2026-11-02"),  # Tuesday
        (datetime(2026, 11, 13, 9, 0, tzinfo=UTC), False, "2026-11-02"),  # Friday: still last week
    ],
    ids=["sun-1759", "sun-1800", "mon", "mon-2359", "tue", "fri"],
)
def test_week_recap_window(admin_client, frozen, now, show, start):
    frozen(now)
    recap = get(admin_client)["week_recap"]
    assert recap["show"] is show
    assert recap["week_start"] == start and recap["week_end"] == "2026-11-08"


def test_week_recap_window_in_summer_time(admin_client, frozen):
    # Sunday 19 July 2026 17:30 BST is 16:30 UTC: still before 18:00 UK
    frozen(datetime(2026, 7, 19, 16, 30, tzinfo=UTC))
    assert get(admin_client)["week_recap"]["show"] is False
    frozen(datetime(2026, 7, 19, 17, 0, tzinfo=UTC))  # 18:00 BST
    recap = get(admin_client)["week_recap"]
    assert recap["show"] is True and recap["week_start"] == "2026-07-13"


def test_week_recap_numbers(admin_client, frozen, db, admin):
    s = strategy(db, admin)
    frozen(datetime(2026, 11, 9, 9, 0, tzinfo=UTC))  # Monday: the week of 2–8 Nov
    trade(db, admin, s, datetime(2026, 11, 3, 9, 0, tzinfo=UTC), r=2.0, pnl=200, rules={"r1": True})
    trade(db, admin, s, datetime(2026, 11, 4, 9, 0, tzinfo=UTC), r=3.0, pnl=300, rules={"r1": True})
    trade(db, admin, s, datetime(2026, 11, 5, 9, 0, tzinfo=UTC), r=-1.0, pnl=-100, rules={"r1": False})
    trade(db, admin, s, datetime(2026, 11, 5, 10, 0, tzinfo=UTC), r=0.0, pnl=2)  # breakeven, unmarked
    trade(db, admin, s, datetime(2026, 10, 30, 9, 0, tzinfo=UTC), r=9.0, pnl=900)  # last-last week
    trade(db, admin, s, datetime(2026, 11, 6, 9, 0, tzinfo=UTC), r=9.0, kind="missed")  # not P&L
    session(db, admin, s, datetime(2026, 11, 4, 9, 0, tzinfo=UTC))
    session(db, admin, s, datetime(2026, 10, 28, 9, 0, tzinfo=UTC))
    recap = get(admin_client)["week_recap"]
    assert recap["show"] is True
    assert recap["sessions"] == 1 and recap["trades"] == 4
    assert recap["total_r"] == 4.0
    assert recap["win_rate"] == pytest.approx(2 / 3, abs=1e-3)  # breakevens left out
    assert recap["rules_kept_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert recap["best_day"] == "Wednesday" and recap["best_day_r"] == 3.0


def test_week_recap_with_nothing_logged(admin_client, frozen):
    frozen(datetime(2026, 11, 9, 9, 0, tzinfo=UTC))
    recap = get(admin_client)["week_recap"]
    assert recap["sessions"] == 0 and recap["trades"] == 0
    assert recap["total_r"] is None and recap["win_rate"] is None and recap["best_day"] is None


# ---- the summary's strategy name for the island ----------------------------------------------


def test_journal_summary_carries_the_strategy_name(admin_client):
    s = new_strategy(admin_client, name="NAS100 silver bullet")
    do_import(admin_client, s["id"], "ideal")
    summary = admin_client.get("/api/journal/summary").json()
    assert summary["last_session"]["strategy_name"] == "NAS100 silver bullet"


# ---- pure helpers ----------------------------------------------------------------------------


def test_streak_helper_counts_runs():
    today = date(2026, 11, 6)
    dates = {date(2026, 11, 6), date(2026, 11, 5), date(2026, 11, 4), date(2026, 10, 1)}
    out = hub_svc.streak(dates, today)
    assert out["current_days"] == 3 and out["best_days"] == 3 and out["active_today"] is True
    assert hub_svc.streak(set(), today)["days"][0]["date"] == "2026-10-10"
