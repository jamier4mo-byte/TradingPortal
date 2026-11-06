"""Team calendar API: recurrence across the UK clock changes, exceptions, completions, permissions."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import make_client, sign_in

UK = ZoneInfo("Europe/London")


def new_task(client, **over):
    body = {
        "title": "Backtest session",
        "start_at": "2026-11-09T09:00:00Z",
        "end_at": "2026-11-09T10:00:00Z",
        "category": "backtesting",
        **over,
    }
    res = client.post("/api/calendar/tasks", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def occurrences(client, frm, to, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    res = client.get(f"/api/calendar/occurrences?from={frm}&to={to}" + (f"&{q}" if q else ""))
    assert res.status_code == 200, res.text
    return res.json()["occurrences"]


def uk(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(UK).strftime("%Y-%m-%d %H:%M")


def utc_hour(iso: str) -> int:
    return datetime.fromisoformat(iso).astimezone(UTC).hour


# ---- recurrence and the clock changes --------------------------------------------------------------


def test_weekly_task_stays_nine_uk_into_summer_time(admin_client):
    # 16 Mar 2026 is GMT (09:00 UK = 09:00Z); the clocks go forward on 29 Mar, so 30 Mar is BST (08:00Z).
    new_task(
        admin_client, start_at="2026-03-16T09:00:00Z", end_at="2026-03-16T10:00:00Z", rrule="FREQ=WEEKLY"
    )
    occ = occurrences(admin_client, "2026-03-16", "2026-04-06")
    assert [o["occurrence_date"] for o in occ] == ["2026-03-16", "2026-03-23", "2026-03-30", "2026-04-06"]
    assert [utc_hour(o["start_at"]) for o in occ] == [9, 9, 8, 8]
    assert all(uk(o["start_at"]).endswith("09:00") for o in occ)
    assert all(uk(o["end_at"]).endswith("10:00") for o in occ)
    assert all(o["recurring"] and not o["exception"] for o in occ)


def test_weekly_task_stays_nine_uk_back_into_winter_time(admin_client):
    # 19 Oct 2026 is BST (08:00Z); the clocks go back on 25 Oct, so 26 Oct is GMT (09:00Z).
    new_task(
        admin_client, start_at="2026-10-19T08:00:00Z", end_at="2026-10-19T10:00:00Z", rrule="FREQ=WEEKLY"
    )
    occ = occurrences(admin_client, "2026-10-19", "2026-11-02")
    assert [utc_hour(o["start_at"]) for o in occ] == [8, 9, 9]
    assert all(uk(o["start_at"]).endswith("09:00") for o in occ)
    # The duration is kept too (two hours either side of the change).
    assert all(uk(o["end_at"]).endswith("11:00") for o in occ)


def test_all_day_task_expands_on_local_dates_across_the_clock_change(admin_client):
    new_task(
        admin_client,
        title="Review",
        all_day=True,
        start_at="2026-03-27T00:00:00Z",
        end_at=None,
        rrule="FREQ=DAILY",
    )
    occ = occurrences(admin_client, "2026-03-27", "2026-03-31")
    assert [o["occurrence_date"] for o in occ] == [
        "2026-03-27",
        "2026-03-28",
        "2026-03-29",
        "2026-03-30",
        "2026-03-31",
    ]
    assert all(o["all_day"] for o in occ)
    # Each starts at UK midnight: 00:00Z in GMT, 23:00Z the evening before once BST starts.
    assert occ[2]["start_at"].startswith("2026-03-29T00:00:00")
    assert occ[3]["start_at"].startswith("2026-03-29T23:00:00")


def test_all_day_task_normalises_start_to_uk_midnight_and_can_span_days(admin_client):
    t = new_task(admin_client, all_day=True, start_at="2026-11-09T14:30:00Z", end_at="2026-11-10T09:00:00Z")
    assert t["start_at"].startswith("2026-11-09T00:00:00")
    assert t["end_at"].startswith(
        "2026-11-11T00:00:00"
    )  # the end rounds up to the midnight after the last day


def test_weekday_rule_skips_the_weekend(admin_client):
    new_task(admin_client, rrule="FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR")
    occ = occurrences(admin_client, "2026-11-09", "2026-11-15")
    assert [o["occurrence_date"] for o in occ] == [
        "2026-11-09",
        "2026-11-10",
        "2026-11-11",
        "2026-11-12",
        "2026-11-13",
    ]


def test_monthly_rule(admin_client):
    new_task(admin_client, start_at="2026-11-01T10:00:00Z", end_at=None, rrule="FREQ=MONTHLY;BYMONTHDAY=1")
    occ = occurrences(admin_client, "2026-11-01", "2026-12-31")
    assert [o["occurrence_date"] for o in occ] == ["2026-11-01", "2026-12-01"]
    assert occ[0]["end_at"] is None


def test_count_and_until_stop_the_series(admin_client):
    new_task(admin_client, title="Three", rrule="FREQ=DAILY;COUNT=3")
    new_task(admin_client, title="Until", rrule="RRULE:FREQ=DAILY;UNTIL=20261111T090000Z")
    occ = occurrences(admin_client, "2026-11-09", "2026-11-30")
    assert [o["occurrence_date"] for o in occ if o["title"] == "Three"] == [
        "2026-11-09",
        "2026-11-10",
        "2026-11-11",
    ]
    assert [o["occurrence_date"] for o in occ if o["title"] == "Until"] == [
        "2026-11-09",
        "2026-11-10",
        "2026-11-11",
    ]


def test_rrule_is_stored_normalised(admin_client):
    t = new_task(admin_client, rrule="rrule:freq=weekly; byday=mo")
    assert t["rrule"] == "FREQ=WEEKLY;BYDAY=MO" and t["recurring"] is True


def test_one_off_task_has_a_single_occurrence_keyed_by_its_uk_date(admin_client):
    t = new_task(admin_client, start_at="2026-11-09T23:30:00Z", end_at=None)  # 23:30 UK in November (GMT)
    occ = occurrences(admin_client, "2026-11-09", "2026-11-09")
    assert [o["id"] for o in occ] == [f"{t['id']}:2026-11-09"]
    assert occ[0]["recurring"] is False and occ[0]["end_at"] is None


# ---- exceptions: this occurrence vs the whole series -------------------------------------------------


def test_editing_this_occurrence_leaves_the_others(admin_client):
    t = new_task(admin_client, rrule="FREQ=WEEKLY")
    res = admin_client.patch(
        f"/api/calendar/tasks/{t['id']}",
        json={"mode": "occurrence", "occurrence_date": "2026-11-16", "title": "Backtest session (NFP week)"},
    )
    assert res.status_code == 200, res.text
    occ = occurrences(admin_client, "2026-11-09", "2026-11-29")
    titles = {o["occurrence_date"]: o["title"] for o in occ}
    assert titles["2026-11-16"] == "Backtest session (NFP week)"
    assert titles["2026-11-09"] == titles["2026-11-23"] == "Backtest session"
    assert next(o for o in occ if o["occurrence_date"] == "2026-11-16")["exception"] is True
    assert admin_client.get(f"/api/calendar/tasks/{t['id']}").json()["title"] == "Backtest session"


def test_editing_the_series_changes_every_occurrence(admin_client):
    t = new_task(admin_client, rrule="FREQ=WEEKLY")
    res = admin_client.patch(
        f"/api/calendar/tasks/{t['id']}", json={"title": "Replay hour", "category": "review"}
    )
    assert res.status_code == 200, res.text
    occ = occurrences(admin_client, "2026-11-09", "2026-11-29")
    assert len(occ) == 3 and all(o["title"] == "Replay hour" and o["category"] == "review" for o in occ)


def test_moved_occurrence_appears_on_its_new_day_only(admin_client):
    t = new_task(admin_client, rrule="FREQ=WEEKLY")
    res = admin_client.patch(
        f"/api/calendar/tasks/{t['id']}",
        json={"mode": "occurrence", "occurrence_date": "2026-11-16", "start_at": "2026-11-18T14:00:00Z"},
    )
    assert res.status_code == 200, res.text
    occ = occurrences(admin_client, "2026-11-09", "2026-11-22")
    by_day = {o["start_at"][:10]: o for o in occ}
    assert set(by_day) == {"2026-11-09", "2026-11-18"}
    moved = by_day["2026-11-18"]
    assert moved["occurrence_date"] == "2026-11-16" and moved["id"] == f"{t['id']}:2026-11-16"
    assert moved["start_at"].startswith("2026-11-18T14:00:00") and moved["end_at"].startswith(
        "2026-11-18T15:00:00"
    )
    # Asking for the original day alone finds nothing; the new day alone finds it.
    assert occurrences(admin_client, "2026-11-16", "2026-11-16") == []
    assert len(occurrences(admin_client, "2026-11-18", "2026-11-18")) == 1


def test_moving_the_series_from_one_occurrence_shifts_every_occurrence(admin_client):
    t = new_task(admin_client, rrule="FREQ=WEEKLY")
    # Drag the 16 Nov occurrence to Tue 17 Nov 10:00: the whole series moves a day and an hour.
    res = admin_client.patch(
        f"/api/calendar/tasks/{t['id']}",
        json={"mode": "series", "occurrence_date": "2026-11-16", "start_at": "2026-11-17T10:00:00Z"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["start_at"].startswith("2026-11-10T10:00:00")
    occ = occurrences(admin_client, "2026-11-09", "2026-11-29")
    assert [o["occurrence_date"] for o in occ] == ["2026-11-10", "2026-11-17", "2026-11-24"]
    assert all(uk(o["start_at"]).endswith("10:00") and uk(o["end_at"]).endswith("11:00") for o in occ)


def test_series_move_across_the_clock_change_keeps_the_uk_wall_time(admin_client):
    t = new_task(
        admin_client, start_at="2026-10-05T08:00:00Z", end_at="2026-10-05T09:00:00Z", rrule="FREQ=WEEKLY"
    )
    # Drag the 26 Oct (GMT) occurrence, shown at 09:00 UK, to 10:00 UK the same day.
    res = admin_client.patch(
        f"/api/calendar/tasks/{t['id']}",
        json={"occurrence_date": "2026-10-26", "start_at": "2026-10-26T10:00:00Z"},
    )
    assert res.status_code == 200, res.text
    occ = occurrences(admin_client, "2026-10-05", "2026-11-02")
    assert all(uk(o["start_at"]).endswith("10:00") for o in occ), [uk(o["start_at"]) for o in occ]


def test_deleting_this_occurrence_hides_only_that_one(admin_client):
    t = new_task(admin_client, rrule="FREQ=WEEKLY")
    res = admin_client.delete(f"/api/calendar/tasks/{t['id']}?mode=occurrence&occurrence_date=2026-11-16")
    assert res.status_code == 200 and "rest of the series" in res.json()["message"]
    occ = occurrences(admin_client, "2026-11-09", "2026-11-29")
    assert [o["occurrence_date"] for o in occ] == ["2026-11-09", "2026-11-23"]
    assert admin_client.get(f"/api/calendar/tasks/{t['id']}").status_code == 200


def test_deleting_the_series_removes_the_task(admin_client, db):
    t = new_task(admin_client, rrule="FREQ=WEEKLY")
    assert admin_client.delete(f"/api/calendar/tasks/{t['id']}").status_code == 200
    assert occurrences(admin_client, "2026-11-09", "2026-11-29") == []
    assert admin_client.get(f"/api/calendar/tasks/{t['id']}").status_code == 404
    assert admin_client.get("/api/calendar/tasks").json() == []
    actions = list(db.scalars(select(AuditLog.action).where(AuditLog.target_id == str(t["id"]))))
    assert "task.created" in actions and "task.deleted" in actions


def test_one_off_task_ignores_mode(admin_client):
    t = new_task(admin_client)
    res = admin_client.patch(
        f"/api/calendar/tasks/{t['id']}",
        json={"mode": "occurrence", "occurrence_date": "2026-11-09", "title": "Moved"},
    )
    assert res.status_code == 200 and res.json()["title"] == "Moved"
    assert (
        admin_client.delete(
            f"/api/calendar/tasks/{t['id']}?mode=occurrence&occurrence_date=2026-11-09"
        ).status_code
        == 200
    )
    assert admin_client.get(f"/api/calendar/tasks/{t['id']}").status_code == 404


def test_occurrence_edit_needs_a_date(admin_client):
    t = new_task(admin_client, rrule="FREQ=WEEKLY")
    assert (
        admin_client.patch(
            f"/api/calendar/tasks/{t['id']}", json={"mode": "occurrence", "title": "x"}
        ).status_code
        == 422
    )
    res = admin_client.patch(
        f"/api/calendar/tasks/{t['id']}",
        json={"mode": "occurrence", "occurrence_date": "2026-11-10", "title": "x"},
    )
    assert res.status_code == 404  # no occurrence on a Tuesday


# ---- completions ------------------------------------------------------------------------------------


def test_complete_and_uncomplete_are_idempotent(admin_client):
    t = new_task(admin_client, rrule="FREQ=WEEKLY")
    for _ in range(2):
        res = admin_client.post(
            f"/api/calendar/tasks/{t['id']}/complete", json={"occurrence_date": "2026-11-16"}
        )
        assert res.status_code == 200, res.text
        assert res.json()["done"] is True and res.json()["completed_by"]["display_name"] == "Jamie"
    occ = {o["occurrence_date"]: o for o in occurrences(admin_client, "2026-11-09", "2026-11-29")}
    assert occ["2026-11-16"]["done"] is True and occ["2026-11-16"]["completed_by"]["display_name"] == "Jamie"
    assert occ["2026-11-09"]["done"] is False and occ["2026-11-09"]["completed_by"] is None
    for _ in range(2):
        res = admin_client.delete(f"/api/calendar/tasks/{t['id']}/complete?occurrence_date=2026-11-16")
        assert res.status_code == 200 and res.json()["done"] is False
    assert all(not o["done"] for o in occurrences(admin_client, "2026-11-09", "2026-11-29"))


def test_completing_a_date_with_no_occurrence_is_404(admin_client):
    t = new_task(admin_client, rrule="FREQ=WEEKLY")
    res = admin_client.post(f"/api/calendar/tasks/{t['id']}/complete", json={"occurrence_date": "2026-11-10"})
    assert res.status_code == 404


def test_a_moved_occurrence_can_still_be_completed_by_its_original_date(admin_client):
    t = new_task(admin_client, rrule="FREQ=WEEKLY")
    admin_client.patch(
        f"/api/calendar/tasks/{t['id']}",
        json={"mode": "occurrence", "occurrence_date": "2026-11-16", "start_at": "2026-11-18T14:00:00Z"},
    )
    res = admin_client.post(f"/api/calendar/tasks/{t['id']}/complete", json={"occurrence_date": "2026-11-16"})
    assert res.status_code == 200
    occ = occurrences(admin_client, "2026-11-18", "2026-11-18")
    assert occ[0]["done"] is True


# ---- listing, filters, limits -----------------------------------------------------------------------


def test_owners_filter_and_owner_list(admin_client, member_client):
    new_task(admin_client, title="Jamie's")
    new_task(member_client, title="Sam's")
    all_occ = occurrences(admin_client, "2026-11-09", "2026-11-09")
    assert sorted(o["title"] for o in all_occ) == ["Jamie's", "Sam's"]
    jamie = all_occ[0]["owner"]["id"] if all_occ[0]["title"] == "Jamie's" else all_occ[1]["owner"]["id"]
    only = occurrences(admin_client, "2026-11-09", "2026-11-09", owners=jamie)
    assert [o["title"] for o in only] == ["Jamie's"]
    res = admin_client.get("/api/calendar/occurrences?from=2026-11-09&to=2026-11-09").json()
    assert {u["display_name"] for u in res["owners"]} == {"Jamie", "Sam"}
    assert res["from"] == "2026-11-09" and res["to"] == "2026-11-09"
    assert (
        admin_client.get("/api/calendar/occurrences?from=2026-11-09&to=2026-11-09&owners=x").status_code
        == 422
    )


def test_sixty_two_day_cap(admin_client):
    assert admin_client.get("/api/calendar/occurrences?from=2026-11-01&to=2027-01-01").status_code == 200
    assert admin_client.get("/api/calendar/occurrences?from=2026-11-01&to=2027-01-02").status_code == 422


def test_default_range_is_the_week_from_today(admin_client):
    res = admin_client.get("/api/calendar/occurrences")
    assert res.status_code == 200
    body = res.json()
    assert body["occurrences"] == []
    assert (datetime.fromisoformat(body["to"]) - datetime.fromisoformat(body["from"])).days == 6


def test_tasks_list_and_scope(admin_client, member_client):
    new_task(admin_client, title="Jamie's")
    new_task(member_client, title="Sam's")
    assert len(admin_client.get("/api/calendar/tasks").json()) == 2
    assert [t["title"] for t in admin_client.get("/api/calendar/tasks?scope=mine").json()] == ["Jamie's"]
    assert [t["title"] for t in member_client.get("/api/calendar/tasks?scope=others").json()] == ["Jamie's"]


# ---- permissions (4.1 / F11) -------------------------------------------------------------------------


def test_member_reads_but_cannot_change_the_admins_task(admin_client, member_client):
    t = new_task(admin_client, rrule="FREQ=WEEKLY")
    occ = occurrences(member_client, "2026-11-09", "2026-11-09")
    assert len(occ) == 1 and occ[0]["can_edit"] is False and occ[0]["owner"]["display_name"] == "Jamie"
    assert member_client.get(f"/api/calendar/tasks/{t['id']}").json()["can_edit"] is False
    assert (
        member_client.patch(f"/api/calendar/tasks/{t['id']}", json={"title": "Mine now"}).status_code == 403
    )
    assert (
        member_client.patch(
            f"/api/calendar/tasks/{t['id']}",
            json={"mode": "occurrence", "occurrence_date": "2026-11-09", "title": "Mine now"},
        ).status_code
        == 403
    )
    assert member_client.delete(f"/api/calendar/tasks/{t['id']}").status_code == 403
    assert (
        member_client.post(
            f"/api/calendar/tasks/{t['id']}/complete", json={"occurrence_date": "2026-11-09"}
        ).status_code
        == 403
    )
    assert (
        member_client.delete(f"/api/calendar/tasks/{t['id']}/complete?occurrence_date=2026-11-09").status_code
        == 403
    )
    assert admin_client.get(f"/api/calendar/tasks/{t['id']}").json()["title"] == "Backtest session"


def test_admin_can_change_and_complete_a_members_task(admin_client, member_client):
    t = new_task(member_client)
    assert (
        admin_client.patch(f"/api/calendar/tasks/{t['id']}", json={"title": "Edited by Jamie"}).status_code
        == 200
    )
    res = admin_client.post(f"/api/calendar/tasks/{t['id']}/complete", json={"occurrence_date": "2026-11-09"})
    assert res.status_code == 200 and res.json()["completed_by"]["display_name"] == "Jamie"
    assert admin_client.delete(f"/api/calendar/tasks/{t['id']}").status_code == 200


def test_member_owns_their_own_task(member_client, other_member):
    t = new_task(member_client)
    assert (
        member_client.patch(f"/api/calendar/tasks/{t['id']}", json={"title": "Still mine"}).status_code == 200
    )
    alex = make_client()
    sign_in(alex, other_member.email)
    assert alex.patch(f"/api/calendar/tasks/{t['id']}", json={"title": "Nope"}).status_code == 403
    assert len(occurrences(alex, "2026-11-09", "2026-11-09")) == 1
    assert member_client.delete(f"/api/calendar/tasks/{t['id']}").status_code == 200


def test_anonymous_gets_401(admin):
    c = make_client()
    assert c.get("/api/calendar/occurrences").status_code == 401
    assert (
        c.post("/api/calendar/tasks", json={"title": "x", "start_at": "2026-11-09T09:00:00Z"}).status_code
        == 401
    )


# ---- validation (422) ---------------------------------------------------------------------------------


def test_validation_errors(admin_client):
    post = lambda **over: admin_client.post(  # noqa: E731
        "/api/calendar/tasks", json={"title": "x", "start_at": "2026-11-09T09:00:00Z", **over}
    )
    assert post(title="").status_code == 422
    assert post(title="   ").status_code == 422
    assert post(end_at="2026-11-09T08:00:00Z").status_code == 422
    assert post(end_at="2026-11-09T09:00:00Z").status_code == 422
    assert post(rrule="FREQ=SOMETIMES").status_code == 422
    assert post(rrule="hello world").status_code == 422
    assert post(category="chores").status_code == 422
    assert post(tz="Mars/Olympus").status_code == 422
    assert admin_client.post("/api/calendar/tasks", json={"title": "x"}).status_code == 422
    t = post().json()
    assert (
        admin_client.post(
            f"/api/calendar/tasks/{t['id']}/complete", json={"occurrence_date": "9 Nov"}
        ).status_code
        == 422
    )
    assert admin_client.delete(f"/api/calendar/tasks/{t['id']}/complete").status_code == 422
    assert admin_client.get("/api/calendar/tasks/999").status_code == 404


def test_task_out_shape(admin_client):
    t = new_task(admin_client, description="  Replay NAS100 ", rrule="FREQ=WEEKLY")
    assert t["owner"]["display_name"] == "Jamie" and t["can_edit"] is True
    assert t["category"] == "backtesting" and t["category_label"] == "Backtesting"
    assert t["description"] == "Replay NAS100" and t["tz"] == "Europe/London"
    assert t["recurring"] is True and t["all_day"] is False


def test_sub_daily_repeat_rules_are_refused(admin_client):
    """A FREQ=MINUTELY rule would expand to thousands of rows per window (denial of service)."""
    body = {"title": "Spam", "start_at": "2026-11-09T09:00:00Z", "end_at": "2026-11-09T10:00:00Z"}
    for rule in (
        "FREQ=MINUTELY",
        "FREQ=HOURLY",
        "FREQ=SECONDLY;COUNT=5",
        "FREQ=DAILY;BYHOUR=0,1,2,3,4,5,6,7,8,9,10,11,12",
        "FREQ=DAILY;BYMINUTE=0,15,30,45",
        "FREQ=WEEKLY;BYSETPOS=1",
    ):
        res = admin_client.post("/api/calendar/tasks", json={**body, "rrule": rule})
        assert res.status_code == 422, (rule, res.text)
    assert admin_client.post("/api/calendar/tasks", json={**body, "rrule": "FREQ=DAILY"}).status_code == 201


def test_expansion_caps_occurrences_per_task(admin_client):
    """Even a daily rule over the longest window stays bounded by MAX_OCCURRENCES_PER_TASK."""
    from app.services import calendar as cal

    body = {
        "title": "Daily",
        "start_at": "2026-01-01T09:00:00Z",
        "end_at": "2026-01-01T10:00:00Z",
        "rrule": "FREQ=DAILY",
    }
    assert admin_client.post("/api/calendar/tasks", json=body).status_code == 201
    res = admin_client.get("/api/calendar/occurrences?from=2026-01-01&to=2026-03-03")
    assert res.status_code == 200
    assert 0 < len(res.json()["occurrences"]) <= cal.MAX_OCCURRENCES_PER_TASK


def test_recurring_start_must_be_within_ten_years(admin_client):
    body = {
        "title": "Old",
        "start_at": "1990-01-01T09:00:00Z",
        "end_at": "1990-01-01T10:00:00Z",
        "rrule": "FREQ=DAILY",
    }
    assert admin_client.post("/api/calendar/tasks", json=body).status_code == 422
    one_off = {k: v for k, v in body.items() if k != "rrule"}
    assert admin_client.post("/api/calendar/tasks", json=one_off).status_code == 201
