"""Quotes, cache, credits, the daily pause, provider choice and the vault's Check key. Frozen clocks;
Twelve Data only through a mock transport serving recorded fixtures."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.settings import get_settings
from app.models import PriceCache, PriceCreditUsage, PriceSymbol, UserApiKey
from app.services.prices import credits as credits_svc
from app.services.prices import service
from app.services.prices.provider import UNAVAILABLE_MESSAGE
from tests.test_prices_support import (  # noqa: F401 — prices_env is a fixture
    KEY,
    NOW,
    give_key,
    load,
    prices_env,
    use_twelve_data,
)

pytestmark = pytest.mark.usefixtures("prices_env")


def credits(db, user, day: date | None = None) -> PriceCreditUsage | None:
    db.expire_all()
    return db.get(PriceCreditUsage, (user.id, day or NOW.date()))


def test_credits_are_charged_to_whoever_fetched_and_the_shared_cache_serves_others(
    monkeypatch, db, member, other_member
) -> None:
    mock = use_twelve_data(monkeypatch)
    give_key(db, member)
    give_key(db, other_member, "td-other-KEY-99999999")
    first = service.get_quote(db, member, "EURUSD", NOW)
    assert first["status"] == "ok" and first["price"] == 1.08502
    assert first["symbol"] == "EUR/USD" and first["code"] == "EURUSD" and first["decimals"] == 5
    assert first["name"] == "Euro / US dollar" and first["unit"] == "pips"
    assert mock.calls == 1
    assert mock.requests[0].headers["Authorization"] == f"apikey {KEY}"

    second = service.get_quote(db, other_member, "EUR/USD", NOW + timedelta(minutes=3))
    assert second["price"] == 1.08502 and second["updated_at"] == first["updated_at"]
    assert mock.calls == 1  # served from the shared cache
    assert credits(db, member).credits == 1
    assert credits(db, other_member) is None  # not charged for the cached answer
    assert db.scalar(select(PriceCache.fetched_by_user_id)) == member.id


def test_cache_prevents_a_repeat_call_within_15_minutes_and_refetches_after(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch)
    give_key(db, member)
    service.get_quote(db, member, "EURUSD", NOW)
    service.get_quote(db, member, "EURUSD", NOW + timedelta(minutes=14, seconds=59))
    assert mock.calls == 1
    again = service.get_quote(db, member, "EURUSD", NOW + timedelta(minutes=15, seconds=1))
    assert mock.calls == 2 and again["status"] == "ok"
    assert credits(db, member).credits == 2


def test_pins_stale_quotes_go_in_one_batched_call(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch)
    give_key(db, member)
    service.add_pin(db, member, "EURUSD")
    service.add_pin(db, member, "BTC/USD")
    quotes = service.pinned_quotes(db, member, NOW)
    assert [q["code"] for q in quotes] == ["EURUSD", "BTCUSD"]
    assert quotes[1]["price"] == 68420.37
    assert mock.calls == 1 and mock.requests[0].url.params["symbol"] == "EUR/USD,BTC/USD"
    assert credits(db, member).credits == 2


def test_search_is_cached_for_24_hours(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch)
    give_key(db, member)
    res = service.search(db, member, "EUR", NOW)
    assert res["cached"] is False
    by_symbol = {r["symbol"]: r for r in res["results"]}
    assert by_symbol["EUR/USD"]["code"] == "EURUSD"  # our seeded alias comes first, with our code
    assert by_symbol["EUR/SEK"]["available"] is False and by_symbol["EUR/SEK"]["code"] is None
    again = service.search(db, member, "eur", NOW + timedelta(hours=23))
    assert again["cached"] is True and mock.calls == 1
    service.search(db, member, "eur", NOW + timedelta(hours=24, minutes=1))
    assert mock.calls == 2


def test_search_never_labels_the_dax_etf_as_ger40(monkeypatch, db, member) -> None:
    use_twelve_data(monkeypatch)
    give_key(db, member)
    results = service.search(db, member, "DAX", NOW)["results"]
    ours = [r for r in results if r["code"] == "GER40"]
    etf = [r for r in results if r["type"] == "ETF"]
    assert len(ours) == 1 and ours[0]["type"] == "index"  # our own alias, from price_symbols
    assert etf and etf[0]["code"] is None


def test_search_with_one_letter_stays_local(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch)
    give_key(db, member)
    service.search(db, member, "g", NOW)
    assert mock.calls == 0


def test_the_minute_limiter_queues_through_the_service(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch)
    give_key(db, member)
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III"]
    for s in symbols:
        assert service.get_quote(db, member, s, NOW)["status"] == "ok"
    assert mock.calls == 9  # the ninth was made, not refused...
    assert service.LIMITER.clock.slept == [pytest.approx(50.25)]  # type: ignore[attr-defined]  # ...after waiting for the next minute
    assert credits(db, member).credits == 9


def test_unavailable_symbol_is_recorded_on_price_symbols(monkeypatch, db, member) -> None:
    use_twelve_data(monkeypatch)
    give_key(db, member)
    gold = service.get_quote(db, member, "XAUUSD", NOW)
    assert gold["status"] == "unavailable" and gold["message"] == UNAVAILABLE_MESSAGE
    assert gold["price"] is None
    eur = service.get_quote(db, member, "EURUSD", NOW)
    db.expire_all()
    rows = {s.code: s for s in db.scalars(select(PriceSymbol))}
    assert rows["XAUUSD"].available is False and rows["XAUUSD"].availability_note == UNAVAILABLE_MESSAGE
    assert rows["XAUUSD"].checked_at is not None
    assert eur["status"] == "ok" and rows["EURUSD"].available is True


def test_an_etf_answer_for_an_index_is_never_shown(monkeypatch, db, member) -> None:
    use_twelve_data(monkeypatch)
    give_key(db, member)
    ger = service.get_quote(db, member, "GER40", NOW)
    assert ger["status"] == "unavailable" and ger["price"] is None
    assert ger["message"] == UNAVAILABLE_MESSAGE
    db.expire_all()
    assert db.scalar(select(PriceSymbol.available).where(PriceSymbol.code == "GER40")) is False


def test_daily_limit_pauses_with_the_last_known_prices(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch)
    give_key(db, member)
    service.get_quote(db, member, "EURUSD", NOW)
    row = credits(db, member)
    row.credits = 800
    db.commit()
    later = NOW + timedelta(minutes=30)
    q = service.get_quote(db, member, "EURUSD", later)
    assert q["status"] == "stale" and q["price"] == 1.08502
    assert q["message"] == "Live data paused – daily limit reached"
    assert mock.calls == 1  # paused: no call
    usage = service.usage(db, member, later)
    assert usage["paused"] is True and usage["paused_reason"] == "Live data paused – daily limit reached"
    assert usage["resets_at"] == datetime(2026, 11, 7, tzinfo=UTC)

    # 00:00 UTC: a new day, live again
    tomorrow = datetime(2026, 11, 7, 0, 5, tzinfo=UTC)
    assert service.usage(db, member, tomorrow)["paused"] is False
    assert service.get_quote(db, member, "EURUSD", tomorrow)["status"] == "ok"
    assert mock.calls == 2
    assert credits(db, member, date(2026, 11, 7)).credits == 1


def test_a_429_for_the_day_pauses_too(monkeypatch, db, member) -> None:
    calls = {"n": 0}

    def route(request):
        calls["n"] += 1
        return (200, load("quote_eurusd.json")) if calls["n"] == 1 else (429, load("error_429_day.json"))

    use_twelve_data(monkeypatch, route)
    give_key(db, member)
    service.get_quote(db, member, "EURUSD", NOW)
    q = service.get_quote(db, member, "EURUSD", NOW + timedelta(minutes=20))
    assert q["status"] == "stale" and q["price"] == 1.08502
    assert service.usage(db, member, NOW + timedelta(minutes=21))["paused"] is True
    service.get_quote(db, member, "BTCUSD", NOW + timedelta(minutes=22))
    assert calls["n"] == 2  # paused: no more calls today


def test_an_invalid_key_shows_an_error_not_a_price(monkeypatch, db, member) -> None:
    use_twelve_data(monkeypatch, lambda r: (401, load("error_401.json")))
    give_key(db, member)
    q = service.get_quote(db, member, "EURUSD", NOW)
    assert q["status"] == "error" and q["price"] is None and KEY not in (q["message"] or "")


def test_sparkline_is_one_credit_and_cached(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch)
    give_key(db, member)
    s = service.get_sparkline(db, member, "EURUSD", NOW)
    assert s["status"] == "ok" and s["interval"] == "15min" and len(s["points"]) == 96
    assert isinstance(s["points"][0]["v"], float)
    params = mock.requests[0].url.params
    assert params["interval"] == "15min" and params["outputsize"] == "96"
    service.get_sparkline(db, member, "EURUSD", NOW + timedelta(minutes=10))
    assert mock.calls == 1 and credits(db, member).credits == 1


# ---- which provider ------------------------------------------------------------------------------


def test_production_without_a_key_is_no_key(monkeypatch, db, member) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "env", "production")
    monkeypatch.setattr(s, "price_provider", "auto")
    monkeypatch.setattr(s, "dev_twelve_data_key", "dev-key-should-be-ignored-1234")
    q = service.get_quote(db, member, "EURUSD", NOW)
    assert q["status"] == "no_key" and q["price"] is None
    u = service.usage(db, member, NOW)
    assert u["provider"] == "twelve_data" and u["has_key"] is False and u["paused"] is False
    assert service.get_sparkline(db, member, "EURUSD", NOW)["status"] == "no_key"


def test_development_without_any_key_uses_the_fake(monkeypatch, db, member) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "env", "development")
    monkeypatch.setattr(s, "price_provider", "auto")
    q = service.get_quote(db, member, "EURUSD", NOW)  # the refusing transport proves no call
    assert q["status"] == "ok" and 1.0 < q["price"] < 1.2
    assert service.usage(db, member, NOW)["provider"] == "fake"
    assert db.scalar(select(PriceCache.key)).startswith("fake:")


def test_development_uses_the_dev_key_when_set(monkeypatch, db, member) -> None:
    mock = use_twelve_data(monkeypatch)
    s = get_settings()
    monkeypatch.setattr(s, "env", "development")
    monkeypatch.setattr(s, "price_provider", "auto")
    monkeypatch.setattr(s, "dev_twelve_data_key", "dev-key-0000-1111")
    q = service.get_quote(db, member, "EURUSD", NOW)
    assert q["status"] == "ok" and mock.requests[0].headers["Authorization"] == "apikey dev-key-0000-1111"
    assert service.usage(db, member, NOW)["has_key"] is True


def test_a_vault_key_never_sees_a_fake_cached_price(monkeypatch, db, member, other_member) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "env", "development")
    monkeypatch.setattr(s, "price_provider", "auto")
    fake = service.get_quote(db, other_member, "EURUSD", NOW)  # no key: the fake
    mock = use_twelve_data(monkeypatch)
    monkeypatch.setattr(s, "price_provider", "auto")
    give_key(db, member)
    real = service.get_quote(db, member, "EURUSD", NOW + timedelta(minutes=1))
    assert mock.calls == 1 and real["price"] == 1.08502 and real["price"] != fake["price"]


# ---- the vault's Check key ------------------------------------------------------------------------


def test_check_key_calls_api_usage_and_reports_credits(monkeypatch, member_client, member, db) -> None:
    mock = use_twelve_data(monkeypatch)
    assert member_client.put("/api/me/keys/twelve_data", json={"key": KEY}).status_code == 200
    res = member_client.post("/api/me/keys/twelve_data/test")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True and body["message"] == "Key works · 12 of 800 credits used today"
    assert mock.paths() == ["/api_usage"] and KEY not in res.text
    row = credits(db, member, datetime.now(UTC).date())
    assert row.credits == 12 and row.provider_reported == 12  # corrected up from our 1


def test_check_key_reports_a_rejected_key(monkeypatch, member_client, db) -> None:
    use_twelve_data(monkeypatch, lambda r: (200, load("error_401.json")))
    member_client.put("/api/me/keys/twelve_data", json={"key": KEY})
    body = member_client.post("/api/me/keys/twelve_data/test").json()
    assert body["ok"] is False and body["message"] == "Twelve Data rejected this key"
    db.expire_all()
    assert db.scalar(select(UserApiKey.last_test_ok)) is False
    assert member_client.get("/api/prices/usage").json()["used"] == 0


def test_credit_day_is_the_utc_date() -> None:
    late = datetime(2026, 11, 6, 23, 59, tzinfo=UTC)
    assert credits_svc.day_of(late) == date(2026, 11, 6)
    assert credits_svc.resets_at(late) == datetime(2026, 11, 7, tzinfo=UTC)


def test_one_users_plan_refusal_is_not_reused_for_another_user(monkeypatch, db, member, other_member) -> None:
    """Plans differ per user: Sam's "not on your plan" must not hide gold from Alex; Alex's key is asked."""
    mock = use_twelve_data(monkeypatch)
    give_key(db, member)
    give_key(db, other_member)
    assert service.get_quote(db, member, "XAUUSD", NOW)["status"] == "unavailable"
    calls = len(mock.requests)
    service.get_quote(db, other_member, "XAUUSD", NOW + timedelta(minutes=1))
    assert len(mock.requests) == calls + 1  # asked again with Alex's own key
    # Sam's answer stays the same (it may cost Sam one more call, since the shared row is now Alex's).
    assert service.get_quote(db, member, "XAUUSD", NOW + timedelta(minutes=2))["status"] == "unavailable"
