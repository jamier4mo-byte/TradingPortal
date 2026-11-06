"""The price-reactions job: opt-in only, leftover credits only, computed once, unavailable skipped."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Event, PriceCreditUsage, PriceReaction, PriceSymbol
from app.services import market_prefs
from app.services.prices import reactions
from app.services.prices.provider import Bar
from tests.test_prices_support import (  # noqa: F401 — prices_env is a fixture
    KEY,
    give_key,
    load,
    prices_env,
    use_twelve_data,
)

pytestmark = pytest.mark.usefixtures("prices_env")

RELEASE = datetime(2026, 11, 5, 13, 30, tzinfo=UTC)
NOW = RELEASE + timedelta(hours=2)


def event(db, currency: str = "USD", at: datetime = RELEASE, impact: str = "high") -> Event:
    e = Event(title="CPI m/m", currency=currency, at=at, impact=impact, sources=["forex_factory"])
    db.add(e)
    db.commit()
    return e


def opt_in(db, user, cap: int = 150) -> None:
    market_prefs.save_prefs(db, user, allow_background_jobs=True, background_daily_cap=cap)


def all_ok(request):
    if request.url.path == "/time_series":
        return 200, load("time_series_1min_eurusd.json")
    raise AssertionError(request.url.path)


def rows(db) -> dict[tuple[str, int], PriceReaction]:
    db.expire_all()
    return {(r.instrument, r.horizon_minutes): r for r in db.scalars(select(PriceReaction))}


def usage(db, user) -> PriceCreditUsage | None:
    db.expire_all()
    return db.get(PriceCreditUsage, (user.id, NOW.date()))


def test_nothing_happens_without_an_opt_in(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch)
    give_key(db, member)
    event(db)
    assert reactions.run(db, NOW) == {"skipped": "no opted-in users"}
    assert mock.calls == 0 and rows(db) == {}


def test_opted_in_user_gets_5_15_60_rows(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch)
    give_key(db, member)
    opt_in(db, member)
    e = event(db)
    result = reactions.run(db, NOW)
    assert result["computed"] == 4  # USD → XAUUSD, BTCUSD, EURUSD, NAS100

    got = rows(db)
    eur5, eur15, eur60 = got[("EURUSD", 5)], got[("EURUSD", 15)], got[("EURUSD", 60)]
    assert eur5.status == "ok" and eur5.unit == "pips" and eur5.event_id == e.id
    assert eur5.open_price == 1.08511 and eur5.high == 1.08554 and eur5.low == 1.08475
    assert (eur5.range_units, eur5.move_units, eur5.direction) == (7.9, -0.3, "flat")
    assert (eur15.range_units, eur15.move_units, eur15.direction) == (18.8, 9.5, "up")
    assert (eur60.range_units, eur60.move_units, eur60.direction) == (34.9, 23.0, "up")
    assert eur60.close_price == 1.08741 and eur60.computed_with_user_id == member.id

    assert {got[("XAUUSD", h)].status for h in (5, 15, 60)} == {"unavailable"}  # Grow plan
    assert {got[("NAS100", h)].status for h in (5, 15, 60)} == {"unavailable"}
    assert {got[("BTCUSD", h)].status for h in (5, 15, 60)} == {"no_data"}
    db.expire_all()
    assert db.scalar(select(PriceSymbol.available).where(PriceSymbol.code == "XAUUSD")) is False

    eur_call = next(r for r in mock.requests if r.url.params["symbol"] == "EUR/USD")
    assert eur_call.url.params["interval"] == "1min"
    assert eur_call.url.params["start_date"] == "2026-11-05 13:30:00"
    assert eur_call.url.params["end_date"] == "2026-11-05 14:31:00"
    assert eur_call.headers["Authorization"] == f"apikey {KEY}"
    u = usage(db, member)
    assert u.background_credits == u.credits == 2  # EUR/USD and BTC/USD answered; refusals cost nothing


def test_reactions_are_computed_once(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch, all_ok)
    give_key(db, member)
    opt_in(db, member)
    event(db)
    reactions.run(db, NOW)
    calls = mock.calls
    assert calls == 4 and len(rows(db)) == 12
    assert reactions.run(db, NOW + timedelta(minutes=1)) == {"computed": 0, "fetched": 0}
    assert mock.calls == calls


def test_too_recent_too_old_and_low_impact_events_are_left_alone(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch, all_ok)
    give_key(db, member)
    opt_in(db, member)
    event(db, at=NOW - timedelta(minutes=60))  # not settled yet
    event(db, at=NOW - timedelta(days=8))  # older than a week
    event(db, impact="medium")
    reactions.run(db, NOW)
    assert mock.calls == 0


def test_the_users_background_cap_is_respected(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch, all_ok)
    give_key(db, member)
    opt_in(db, member, cap=2)
    event(db)
    reactions.run(db, NOW)
    reactions.run(db, NOW + timedelta(minutes=1))
    assert mock.calls == 2 and usage(db, member).background_credits == 2


def test_the_reserve_for_watchlist_and_search_is_kept(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch, all_ok)
    give_key(db, member)
    opt_in(db, member)
    event(db)
    db.add(PriceCreditUsage(user_id=member.id, day=NOW.date(), credits=599, background_credits=0, requests=1))
    db.commit()
    reactions.run(db, NOW)
    assert mock.calls == 1  # 800 − 200 reserve − 599 used = 1 leftover credit
    assert usage(db, member).credits == 600
    reactions.run(db, NOW + timedelta(minutes=1))
    assert mock.calls == 1  # nothing left over now


def test_unavailable_instruments_are_skipped(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch, all_ok)
    give_key(db, member)
    opt_in(db, member)
    gold = db.scalar(select(PriceSymbol).where(PriceSymbol.code == "XAUUSD"))
    gold.available = False
    db.commit()
    event(db)
    reactions.run(db, NOW)
    assert "XAU/USD" not in {r.url.params["symbol"] for r in mock.requests}
    assert ("XAUUSD", 5) not in rows(db)


def test_at_most_five_series_per_tick_and_users_take_turns(monkeypatch, db, member, other_member) -> None:
    mock = use_twelve_data(monkeypatch, all_ok)
    give_key(db, member)
    give_key(db, other_member, "td-other-KEY-99999999")
    opt_in(db, member)
    opt_in(db, other_member)
    event(db)
    event(db, at=RELEASE + timedelta(minutes=30))
    result = reactions.run(db, NOW)
    assert result["fetched"] == 5 and mock.calls == 5
    keys = [r.headers["Authorization"] for r in mock.requests]
    assert keys[:2] == [f"apikey {KEY}", "apikey td-other-KEY-99999999"]  # alternate
    assert usage(db, member).background_credits == 3 and usage(db, other_member).background_credits == 2
    reactions.run(db, NOW + timedelta(minutes=1))
    assert mock.calls == 8
    db.expire_all()
    assert len(db.scalars(select(PriceReaction)).all()) == 2 * 4 * 3


def test_the_fake_computes_reactions_in_development(db, member) -> None:
    opt_in(db, member)  # the default test provider is the fake
    event(db, currency="EUR")
    reactions.run(db, NOW)
    got = rows(db)
    assert got[("EURUSD", 15)].status == "ok" and got[("EURUSD", 15)].range_units > 0
    assert got[("GER40", 15)].status == "unavailable"  # the fake refuses DAX, as Twelve Data does
    db.expire_all()
    # the fake's answers are never recorded as Twelve Data availability
    assert db.scalar(select(PriceSymbol.available).where(PriceSymbol.code == "GER40")) is None


def test_compute_in_points() -> None:
    t = RELEASE
    bars = [
        Bar(t - timedelta(minutes=1), 2600.0, 2700.0, 2500.0, 2650.0),  # before the release: ignored
        Bar(t, 2650.0, 2652.5, 2648.0, 2651.0),
        Bar(t + timedelta(minutes=4), 2651.0, 2656.0, 2650.0, 2655.3),
        Bar(t + timedelta(minutes=5), 2655.3, 2670.0, 2655.0, 2669.0),  # only in 15 and 60
    ]
    out = reactions.compute(bars, t, pip_size=0.1)
    assert out[5].open == 2650.0 and out[5].close == 2655.3
    assert out[5].range_units == 80.0 and out[5].move_units == 53.0 and out[5].direction == "up"
    assert out[15].range_units == 220.0 and out[15].move_units == 190.0
    assert reactions.compute([], t, 0.1)[60].status == "no_data"
    flat = reactions.compute([Bar(t, 1.0, 1.00005, 0.99995, 1.00005)], t, 0.0001)[5]
    assert flat.direction == "flat" and flat.move_units == 0.5
