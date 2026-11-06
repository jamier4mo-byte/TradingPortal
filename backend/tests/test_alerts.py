"""Push alerts job (`alerts.run_due`) with a frozen clock and the fake push service. No network."""

import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import session_factory
from app.models import AlertDelivery, AlertPrefs, Event, PushSubscription, UserMarketPrefs
from app.services import alerts, push, scheduler
from app.services.http import NetworkBlocked

from .conftest import make_user

# 6 Nov 2026 is GMT, so UK time = UTC. Event at 13:30; a 15-minute alert is due from 13:15.
AT = datetime(2026, 11, 6, 13, 30, tzinfo=UTC)
DUE = AT - timedelta(minutes=15)
MIN = timedelta(minutes=1)
ALERTS_JOB = [("alerts", "app.services.alerts:run_due")]


@pytest.fixture
def fake(monkeypatch) -> push.FakePushSender:
    sender = push.FakePushSender()
    monkeypatch.setattr(push, "get_sender", lambda: sender)
    return sender


@pytest.fixture
def user(db):
    return make_user(db, email="sam@example.test", name="Sam")


def add_event(db, *, at=AT, currency="USD", impact="high", title="CPI m/m", all_day=False, **kw) -> Event:
    ev = Event(
        title=title,
        currency=currency,
        at=at,
        impact=impact,
        all_day=all_day,
        forecast=kw.get("forecast", "0.3%"),
        previous=kw.get("previous", "0.2%"),
        sources=["forex_factory"],
    )
    db.add(ev)
    db.commit()
    return ev


def add_sub(db, user, endpoint="https://push.example.test/a", label="Phone") -> PushSubscription:
    sub = PushSubscription(
        user_id=user.id, endpoint=endpoint, p256dh="p" * 20, auth="a" * 10, device_label=label
    )
    db.add(sub)
    db.commit()
    return sub


def enable(db, user, **kw) -> AlertPrefs:
    prefs = AlertPrefs(
        user_id=user.id,
        enabled=True,
        minutes_before=kw.get("minutes_before", 15),
        currencies=kw.get("currencies"),
        impacts=kw.get("impacts", ["high"]),
        quiet_start=kw.get("quiet_start"),
        quiet_end=kw.get("quiet_end"),
        chime=kw.get("chime", False),
    )
    db.add(prefs)
    db.commit()
    return prefs


def deliveries(db) -> list[AlertDelivery]:
    db.expire_all()
    return list(db.scalars(select(AlertDelivery).order_by(AlertDelivery.id)))


# ---- sending once ------------------------------------------------------------------------------


def test_a_due_alert_is_sent_exactly_once(db, user, fake):
    enable(db, user, chime=True)
    sub = add_sub(db, user)
    ev = add_event(db)

    first = alerts.run_due(db, DUE)
    second = alerts.run_due(db, DUE + MIN)

    assert first["sent"] == 1 and second["sent"] == 0
    assert len(fake.calls) == 1
    endpoint, payload = fake.calls[0]
    assert endpoint == sub.endpoint
    assert payload == {
        "title": "USD CPI m/m in 15 min",
        "body": "High impact · 13:30 UK · forecast 0.3% · previous 0.2%",
        "url": f"/news/events/{ev.id}",
        "tag": f"event-{ev.id}",
        "event_id": ev.id,
        "chime": True,
    }
    [d] = deliveries(db)
    assert (d.subscription_id, d.event_id, d.status) == (sub.id, ev.id, "sent")
    db.refresh(sub)
    assert sub.last_success_at is not None


def test_a_second_device_gets_its_own_alert(db, user, fake):
    enable(db, user)
    a = add_sub(db, user, "https://push.example.test/a")
    add_event(db)
    alerts.run_due(db, DUE)
    b = add_sub(db, user, "https://push.example.test/b", label="Laptop")
    alerts.run_due(db, DUE + MIN)
    assert len(fake.sent_to(a.endpoint)) == 1
    assert len(fake.sent_to(b.endpoint)) == 1
    assert fake.sent_to(b.endpoint)[0]["title"] == "USD CPI m/m in 14 min"


def test_british_summer_time_is_shown_in_uk_time(db, user, fake):
    enable(db, user)
    add_sub(db, user)
    summer = datetime(2026, 7, 1, 12, 30, tzinfo=UTC)  # 13:30 BST
    add_event(db, at=summer, forecast=None, previous=None)
    alerts.run_due(db, summer - timedelta(minutes=15))
    assert fake.calls[0][1]["body"] == "High impact · 13:30 UK"


# ---- timing ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "sent"),
    [
        (DUE - MIN, False),  # before the alert moment
        (DUE, True),
        (DUE + timedelta(minutes=9), True),  # a late tick still sends within 10 minutes
        (DUE + timedelta(minutes=11), False),  # too stale (e.g. after a long restart)
        (AT, False),  # the event has started
        (AT + MIN, False),
    ],
)
def test_sent_only_inside_the_alert_window(db, user, fake, now, sent):
    enable(db, user)
    add_sub(db, user)
    add_event(db)
    alerts.run_due(db, now)
    assert bool(fake.calls) is sent


def test_minutes_before_is_per_user(db, user, fake):
    enable(db, user, minutes_before=60)
    add_sub(db, user)
    add_event(db)
    alerts.run_due(db, DUE)  # 15 min before: past the 60-minute moment by 45 minutes, too stale
    assert not fake.calls
    alerts.run_due(db, AT - timedelta(minutes=60))
    assert fake.calls[0][1]["title"] == "USD CPI m/m in 60 min"


# ---- filtering ---------------------------------------------------------------------------------


def test_default_impacts_are_high_only(db, user, fake):
    enable(db, user)
    add_sub(db, user)
    add_event(db, impact="medium")
    add_event(db, impact="low", title="Low thing")
    alerts.run_due(db, DUE)
    assert not fake.calls


def test_chosen_impacts(db, user, fake):
    enable(db, user, impacts=["medium"])
    add_sub(db, user)
    add_event(db, impact="high", title="High one")
    med = add_event(db, impact="medium", title="Med one")
    alerts.run_due(db, DUE)
    assert [p["event_id"] for _, p in fake.calls] == [med.id]
    assert fake.calls[0][1]["body"].startswith("Med impact")


def test_all_day_and_holiday_events_are_skipped(db, user, fake):
    enable(db, user, impacts=["high", "medium", "low"])
    add_sub(db, user)
    add_event(db, all_day=True)
    add_event(db, impact="holiday", title="Bank Holiday")
    alerts.run_due(db, DUE)
    assert not fake.calls


def test_currencies_none_follow_the_default_instruments(db, user, fake):
    """No market prefs row: the default instruments (EURUSD, XAUUSD… map to USD; GBPUSD to GBP)."""
    enable(db, user)
    add_sub(db, user)
    usd = add_event(db, currency="USD")
    gbp = add_event(db, currency="GBP", title="GDP q/q")
    add_event(db, currency="CNY", title="CNY thing")
    alerts.run_due(db, DUE)
    assert sorted(p["event_id"] for _, p in fake.calls) == sorted([usd.id, gbp.id])
    assert {"USD", "GBP", "EUR", "JPY"} <= alerts.effective_currencies(db, alerts.get_prefs(db, user))


def test_currencies_none_follow_my_instruments(db, user, fake):
    db.add(UserMarketPrefs(user_id=user.id, instruments=["GBPUSD"]))
    db.commit()
    enable(db, user)
    add_sub(db, user)
    add_event(db, currency="USD")  # USD maps to XAUUSD, BTCUSD, EURUSD, NAS100, not GBPUSD
    gbp = add_event(db, currency="GBP", title="GDP q/q")
    alerts.run_due(db, DUE)
    assert [p["event_id"] for _, p in fake.calls] == [gbp.id]


def test_explicit_currencies(db, user, fake):
    enable(db, user, currencies=["JPY"])
    add_sub(db, user)
    add_event(db, currency="USD")
    jpy = add_event(db, currency="JPY", title="BOJ Policy Rate")
    alerts.run_due(db, DUE)
    assert [p["event_id"] for _, p in fake.calls] == [jpy.id]


def test_disabled_or_deviceless_users_get_nothing(db, user, fake):
    other = make_user(db, email="alex@example.test")
    prefs = enable(db, user)
    prefs.enabled = False
    db.commit()
    add_sub(db, user)
    enable(db, other)  # enabled, but no device
    add_event(db)
    out = alerts.run_due(db, DUE)
    assert not fake.calls and out["users"] == 0


# ---- quiet hours -------------------------------------------------------------------------------


def test_quiet_hours_skip_and_record(db, user, fake):
    enable(db, user, quiet_start="13:00", quiet_end="14:00")
    sub = add_sub(db, user)
    ev = add_event(db)
    out = alerts.run_due(db, DUE)
    assert out["quiet"] == 1 and not fake.calls
    [d] = deliveries(db)
    assert (d.subscription_id, d.event_id, d.status) == (sub.id, ev.id, "skipped_quiet")
    alerts.run_due(db, DUE + MIN)
    assert not fake.calls  # recorded once, never sent late


@pytest.mark.parametrize(
    ("event_at", "quiet"),
    [
        (datetime(2026, 11, 6, 23, 30, tzinfo=UTC), True),  # after the start, before midnight
        (datetime(2026, 11, 7, 6, 30, tzinfo=UTC), True),  # after midnight, before the end
        (datetime(2026, 11, 7, 7, 30, tzinfo=UTC), False),  # the alert at 07:15 is after the end
        (datetime(2026, 11, 6, 21, 30, tzinfo=UTC), False),
    ],
)
def test_quiet_hours_wrap_past_midnight(db, user, fake, event_at, quiet):
    enable(db, user, quiet_start="22:00", quiet_end="07:00")
    add_sub(db, user)
    add_event(db, at=event_at)
    out = alerts.run_due(db, event_at - timedelta(minutes=15))
    assert out["quiet"] == int(quiet)
    assert bool(fake.calls) is not quiet


def test_quiet_hours_use_uk_summer_time():
    prefs = AlertPrefs(user_id=1, quiet_start="22:00", quiet_end="07:00")
    assert alerts.in_quiet_hours(prefs, datetime(2026, 7, 1, 21, 30, tzinfo=UTC))  # 22:30 BST
    assert not alerts.in_quiet_hours(prefs, datetime(2026, 7, 1, 20, 30, tzinfo=UTC))  # 21:30 BST
    assert not alerts.in_quiet_hours(AlertPrefs(user_id=1), datetime(2026, 7, 1, 23, 0, tzinfo=UTC))


# ---- failures ----------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [404, 410])
def test_dead_subscriptions_are_pruned(db, user, fake, status):
    enable(db, user)
    dead = add_sub(db, user, "https://push.example.test/dead")
    live = add_sub(db, user, "https://push.example.test/live")
    fake.statuses[dead.endpoint] = status
    add_event(db)
    out = alerts.run_due(db, DUE)
    assert out["pruned"] == 1 and out["sent"] == 1
    db.expire_all()
    assert db.get(PushSubscription, dead.id) is None
    assert db.get(PushSubscription, live.id) is not None
    assert [d.subscription_id for d in deliveries(db)] == [live.id]


def test_other_failures_are_recorded_and_not_retried(db, user, fake):
    enable(db, user)
    sub = add_sub(db, user)
    fake.statuses[sub.endpoint] = 500
    add_event(db)
    out = alerts.run_due(db, DUE)
    assert out["failed"] == 1
    alerts.run_due(db, DUE + MIN)
    alerts.run_due(db, DUE + 2 * MIN)
    assert len(fake.calls) == 1
    [d] = deliveries(db)
    assert d.status == "failed"
    db.refresh(sub)
    assert sub.last_error == "Push service answered 500"


def test_nothing_happens_without_vapid(db, user):
    enable(db, user)
    add_sub(db, user)
    add_event(db)
    assert alerts.run_due(db, DUE)["skipped"] == "push not configured"
    assert deliveries(db) == []


def test_the_real_sender_refuses_to_send_in_tests():
    from app.vapid_cli import generate_pair

    public, private = generate_pair()
    sender = push.WebPushSender(private, "mailto:you@example.com", public)
    with pytest.raises(NetworkBlocked):
        sender.send(PushSubscription(endpoint="https://push.example.test/x", p256dh="p", auth="a"), {})


# ---- several processes -------------------------------------------------------------------------


def _race(target, n=2):
    barrier = threading.Barrier(n)
    results: list = [None] * n
    errors: list[BaseException] = []

    def worker(i):
        try:
            with session_factory()() as s:
                barrier.wait()
                results[i] = target(s, i)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    return results


def test_two_schedulers_ticking_at_once_send_once(db, user, fake):
    enable(db, user)
    add_sub(db, user, "https://push.example.test/a")
    add_sub(db, user, "https://push.example.test/b")
    add_event(db)
    results = _race(lambda s, i: scheduler.tick(s, now=DUE, holder=f"proc-{i}", jobs=ALERTS_JOB))
    assert sorted("skipped" in r for r in results) == [False, True]
    assert len(fake.calls) == 2  # one per device
    assert len({e for e, _ in fake.calls}) == 2


def test_the_delivery_row_dedupes_even_without_the_lease(db, user, fake):
    """Two run_due calls at once (e.g. a lease handover mid-tick): the unique constraint wins."""
    enable(db, user)
    add_sub(db, user, "https://push.example.test/a")
    add_sub(db, user, "https://push.example.test/b")
    add_event(db)
    results = _race(lambda s, i: alerts.run_due(s, DUE), n=4)
    assert sum(r["sent"] for r in results) == 2
    assert len(fake.calls) == 2
    assert len(deliveries(db)) == 2
