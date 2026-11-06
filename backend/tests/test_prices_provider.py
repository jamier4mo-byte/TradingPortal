"""The provider layer: Twelve Data parsing and errors (recorded fixtures, mock transport), the fake, and
the per-minute limiter. No network."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.services.prices.fake import FakePriceProvider
from app.services.prices.limiter import MinuteLimiter
from app.services.prices.provider import UNAVAILABLE_MESSAGE, ProviderError, Quote, TwelveDataProvider
from tests.test_prices_support import KEY, FakeClock, TwelveDataMock, load


def td(route) -> tuple[TwelveDataProvider, TwelveDataMock]:
    mock = TwelveDataMock(route)
    return TwelveDataProvider(KEY, transport=mock.transport), mock


def test_quote_strings_become_floats_and_the_key_stays_in_the_header() -> None:
    p, mock = td(
        lambda r: (200, load("quote_eurusd.json"), {"api-credits-used": "1", "api-credits-left": "7"})
    )
    res = p.quote(["EUR/USD"])
    q = res.data["EUR/USD"]
    assert isinstance(q, Quote)
    assert q.price == 1.08502 and q.change == 0.00512 and q.percent_change == 0.47412
    assert q.open == 1.0798 and q.high == 1.0862 and q.low == 1.0791 and q.previous_close == 1.0799
    assert q.is_market_open is True and q.decimals == 5
    assert q.market_time == datetime(2026, 11, 6, 13, 45, tzinfo=UTC)
    assert res.credits == 1 and res.minute_left == 7
    req = mock.requests[0]
    assert req.headers["Authorization"] == f"apikey {KEY}"
    assert KEY not in str(req.url)
    assert KEY not in repr(p)


def test_batch_quote_costs_one_credit_per_symbol() -> None:
    p, mock = td(lambda r: (200, load("quote_batch.json")))
    res = p.quote(["EUR/USD", "BTC/USD"])
    assert res.credits == 2 and mock.calls == 1
    assert mock.requests[0].url.params["symbol"] == "EUR/USD,BTC/USD"
    assert res.data["BTC/USD"].price == 68420.37  # type: ignore[union-attr]
    assert res.data["EUR/USD"].price == 1.08502  # type: ignore[union-attr]


def test_batch_quote_with_one_refused_symbol() -> None:
    body = {"EUR/USD": load("quote_eurusd.json"), "XAU/USD": load("error_404_plan.json")}
    p, _ = td(lambda r: (200, body))
    res = p.quote(["EUR/USD", "XAU/USD"])
    err = res.data["XAU/USD"]
    assert isinstance(err, ProviderError) and err.kind == "plan" and err.message == UNAVAILABLE_MESSAGE


@pytest.mark.parametrize(
    ("fixture", "http_status", "kind"),
    [
        ("error_401.json", 200, "invalid_key"),  # errors may come with HTTP 200
        ("error_401.json", 401, "invalid_key"),
        ("error_404_plan.json", 200, "plan"),
        ("error_404_not_found.json", 200, "not_found"),
        ("error_429_minute.json", 200, "minute_limit"),
        ("error_429_day.json", 429, "daily_limit"),
    ],
)
def test_error_bodies_are_classified(fixture, http_status, kind) -> None:
    p, _ = td(lambda r: (http_status, load(fixture)))
    with pytest.raises(ProviderError) as info:
        p.quote(["EUR/USD"])
    assert info.value.kind == kind
    assert KEY not in info.value.message


def test_403_is_a_plan_refusal() -> None:
    p, _ = td(lambda r: (200, {"code": 403, "message": "upgrade", "status": "error"}))
    with pytest.raises(ProviderError) as info:
        p.time_series("XAU/USD", "1min")
    assert info.value.kind == "plan"


def test_network_errors_never_carry_the_key() -> None:
    def boom(request):
        raise httpx.ConnectError("connection refused")

    p = TwelveDataProvider(KEY, transport=httpx.MockTransport(boom))
    with pytest.raises(ProviderError) as info:
        p.usage()
    assert info.value.kind == "error" and KEY not in str(info.value)


def test_time_series_parses_sorted_utc_bars() -> None:
    p, mock = td(lambda r: (200, load("time_series_1min_eurusd.json")))
    start = datetime(2026, 11, 5, 13, 30, tzinfo=UTC)
    res = p.time_series("EUR/USD", "1min", start=start, end=start + timedelta(minutes=61), outputsize=90)
    params = mock.requests[0].url.params
    assert params["start_date"] == "2026-11-05 13:30:00" and params["end_date"] == "2026-11-05 14:31:00"
    assert params["timezone"] == "UTC" and params["outputsize"] == "90"
    assert len(res.data) == 62 and res.credits == 1
    assert res.data[0].t == datetime(2026, 11, 5, 13, 29, tzinfo=UTC)
    assert all(a.t < b.t for a, b in zip(res.data, res.data[1:], strict=False))
    assert isinstance(res.data[0].open, float)


def test_no_data_is_an_empty_series_not_an_error() -> None:
    p, _ = td(lambda r: (200, load("error_400_no_data.json")))
    assert p.time_series("EUR/USD", "1min").data == []


def test_search_reads_plan_access() -> None:
    p, _ = td(lambda r: (200, load("symbol_search_eur.json")))
    hits = {h.symbol: h for h in p.search("eur").data}
    assert hits["EUR/USD"].available is True and hits["EUR/USD"].name == "Euro / US Dollar"
    assert hits["EUR/SEK"].available is False  # Grow plan
    assert hits["EURN"].type == "Common Stock"


def test_usage_parses() -> None:
    p, mock = td(lambda r: (200, load("api_usage.json")))
    res = p.usage()
    assert res.data.used_today == 12 and res.data.daily_limit == 800 and res.credits == 1
    assert mock.paths() == ["/api_usage"]


# ---- the fake --------------------------------------------------------------------------------------


def test_fake_is_deterministic_within_a_bucket_and_moves_between_buckets() -> None:
    t = datetime(2026, 11, 6, 13, 46, tzinfo=UTC)
    a = FakePriceProvider(clock=lambda: t).quote(["EUR/USD"]).data["EUR/USD"]
    b = FakePriceProvider(clock=lambda: t + timedelta(minutes=5)).quote(["EUR/USD"]).data["EUR/USD"]
    c = FakePriceProvider(clock=lambda: t + timedelta(minutes=15)).quote(["EUR/USD"]).data["EUR/USD"]
    assert a == b
    assert a.price != c.price  # type: ignore[union-attr]
    assert 1.0 < a.price < 1.2  # type: ignore[union-attr,operator]


def test_fake_refuses_dax_but_has_ndx() -> None:
    fake = FakePriceProvider(clock=lambda: datetime(2026, 11, 6, 15, tzinfo=UTC))
    data = fake.quote(["DAX", "NDX"]).data
    assert isinstance(data["DAX"], ProviderError) and data["DAX"].message == UNAVAILABLE_MESSAGE
    assert isinstance(data["NDX"], Quote)
    with pytest.raises(ProviderError):
        fake.time_series("DAX", "1min")
    hits = {h.symbol: h.available for h in fake.search("dax").data}
    assert hits == {"DAX": False}


def test_fake_minute_bars_cover_the_window() -> None:
    release = datetime(2026, 11, 5, 13, 30, tzinfo=UTC)
    fake = FakePriceProvider(clock=lambda: release + timedelta(hours=2))
    bars = fake.time_series(
        "XAU/USD", "1min", start=release, end=release + timedelta(minutes=61), outputsize=90
    ).data
    assert bars[0].t == release and len(bars) == 62
    assert all(b.low <= min(b.open, b.close) and b.high >= max(b.open, b.close) for b in bars)


# ---- the per-minute limiter --------------------------------------------------------------------------


def test_limiter_queues_the_ninth_request_until_the_next_minute() -> None:
    clock = FakeClock(datetime(2026, 11, 6, 13, 45, 10, tzinfo=UTC))
    lim = MinuteLimiter(clock=clock, sleep=clock.sleep)
    for _ in range(8):
        assert lim.acquire("user:1") == 0
    waited = lim.acquire("user:1")
    assert waited == pytest.approx(50.25)  # until 13:46:00, plus a safety margin
    assert clock.now >= datetime(2026, 11, 6, 13, 46, tzinfo=UTC)
    assert lim.acquire("user:2") == 0  # another key has its own window


def test_limiter_can_skip_instead_of_waiting_and_honours_the_header() -> None:
    clock = FakeClock()
    lim = MinuteLimiter(clock=clock, sleep=clock.sleep)
    assert lim.acquire("k", 8) == 0
    assert lim.acquire("k", 1, block=False) is None
    assert clock.slept == []
    other = MinuteLimiter(clock=clock, sleep=clock.sleep)
    other.acquire("k", 1)
    other.note_left("k", 0)  # Twelve Data says the minute is spent
    assert other.acquire("k", 1, block=False) is None


def test_only_a_few_requests_per_key_may_wait_for_the_next_minute() -> None:
    """A user can't tie up the server's threads: beyond MAX_WAITERS waiting requests, the rest are refused
    at once (the service then serves the last known price)."""
    import threading

    from app.services.prices.limiter import MAX_WAITERS, MinuteLimiter

    gate = threading.Event()
    lim = MinuteLimiter(per_minute=1, sleep=lambda s: gate.wait(5))
    assert lim.acquire("user:1") == 0.0  # the minute is now full
    waiting = [threading.Thread(target=lim.acquire, args=("user:1",)) for _ in range(MAX_WAITERS)]
    for t in waiting:
        t.start()
    deadline = __import__("time").monotonic() + 2
    while lim._waiting.get("user:1", 0) < MAX_WAITERS and __import__("time").monotonic() < deadline:
        pass
    assert lim.acquire("user:1") is None  # refused, not queued
    assert lim.acquire("user:2") == 0.0  # other keys are unaffected
    gate.set()
    for t in waiting:
        t.join(5)
