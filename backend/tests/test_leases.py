"""DB leases and rate slots: single scheduler, one JBlanked request per 5 minutes globally."""

import threading
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.db import session_factory
from app.services import http, leases, scheduler

T0 = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)


def test_slot_allows_one_claim_per_interval(db):
    five = timedelta(minutes=5)
    assert leases.claim_slot(db, "jblanked", five, now=T0)
    assert not leases.claim_slot(db, "jblanked", five, now=T0 + timedelta(seconds=1))
    assert not leases.claim_slot(db, "jblanked", five, now=T0 + timedelta(minutes=4, seconds=59))
    assert leases.claim_slot(db, "jblanked", five, now=T0 + timedelta(minutes=5))


def test_slot_is_exclusive_across_concurrent_sessions():
    """Ten threads, each with its own DB session (as separate processes would have): one wins."""
    wins: list[bool] = []
    barrier = threading.Barrier(10)

    def worker():
        with session_factory()() as s:
            barrier.wait()
            wins.append(leases.claim_slot(s, "race", timedelta(minutes=5), now=T0))

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert wins.count(True) == 1


def test_lease_is_renewed_by_its_holder_and_taken_over_after_expiry(db):
    ttl = timedelta(minutes=3)
    assert leases.hold(db, "scheduler", "a", ttl, now=T0)
    assert not leases.hold(db, "scheduler", "b", ttl, now=T0 + timedelta(minutes=1))
    assert leases.hold(db, "scheduler", "a", ttl, now=T0 + timedelta(minutes=2))  # renewal
    assert not leases.hold(db, "scheduler", "b", ttl, now=T0 + timedelta(minutes=4))
    assert leases.hold(db, "scheduler", "b", ttl, now=T0 + timedelta(minutes=6))  # a stopped renewing


def test_second_scheduler_skips_its_tick(db):
    calls: list[str] = []
    jobs = [("probe", "tests.test_leases:_probe_job")]
    _PROBE.clear()
    first = scheduler.tick(db, now=T0, holder="proc-a", jobs=jobs)
    second = scheduler.tick(db, now=T0 + timedelta(seconds=30), holder="proc-b", jobs=jobs)
    calls.extend(_PROBE)
    assert first == {"probe": {"ok": True}}
    assert second == {"skipped": "lease held by another process"}
    assert calls == ["ran"]


def test_a_failing_job_does_not_stop_the_others(db):
    _PROBE.clear()
    out = scheduler.tick(
        db,
        now=T0,
        holder="proc-a",
        jobs=[("boom", "tests.test_leases:_failing_job"), ("probe", "tests.test_leases:_probe_job")],
    )
    assert out["boom"] == {"error": "RuntimeError"}
    assert out["probe"] == {"ok": True}


def test_real_network_is_blocked_in_tests():
    with http.client() as c, pytest.raises(http.NetworkBlocked):
        c.get("https://api.twelvedata.com/quote")
    ok = httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True}))
    with http.client(transport=ok) as c:
        res = c.get("https://example.test/")
        assert res.json() == {"ok": True}
        assert res.request.headers["User-Agent"] == "TradingPortal/1.0"


_PROBE: list[str] = []


def _probe_job(db, now):
    _PROBE.append("ran")
    return {"ok": True}


def _failing_job(db, now):
    raise RuntimeError("feed changed shape")
