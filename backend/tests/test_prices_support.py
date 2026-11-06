"""Shared helpers for the price tests (no tests here). Nothing ever reaches Twelve Data: the provider is
the fake, or Twelve Data through an httpx.MockTransport serving recorded-style fixtures."""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.core.settings import get_settings
from app.db import session_factory
from app.models import PriceSymbol
from app.services import keys as keys_svc
from app.services.prices import service
from app.services.prices.limiter import MinuteLimiter

FIXTURES = Path(__file__).parent / "fixtures" / "twelvedata"
KEY = "td-test-KEY-0123456789abcdef"
NOW = datetime(2026, 11, 6, 13, 45, 10, tzinfo=UTC)


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class FakeClock:
    """A clock and a sleep that advances it, so limiter waits take no time."""

    def __init__(self, now: datetime = NOW) -> None:
        self.now = now
        self.slept: list[float] = []

    def __call__(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += timedelta(seconds=seconds)


Route = Callable[[httpx.Request], tuple[int, dict | list] | tuple[int, dict | list, dict]]


class TwelveDataMock:
    """A MockTransport standing in for api.twelvedata.com. Counts calls and keeps every request."""

    def __init__(self, route: Route) -> None:
        self.route = route
        self.requests: list[httpx.Request] = []
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.twelvedata.com"
        self.requests.append(request)
        out = self.route(request)
        status, body = out[0], out[1]
        headers = out[2] if len(out) > 2 else {}  # type: ignore[misc]
        return httpx.Response(status, json=body, headers=headers)

    @property
    def calls(self) -> int:
        return len(self.requests)

    def paths(self) -> list[str]:
        return [r.url.path for r in self.requests]


def default_route(request: httpx.Request) -> tuple[int, dict]:
    """Recorded answers by path and symbol."""
    path, symbol = request.url.path, request.url.params.get("symbol", "")
    if path == "/quote":
        if symbol == "EUR/USD":
            return 200, load("quote_eurusd.json")
        if symbol == "EUR/USD,BTC/USD":
            return 200, load("quote_batch.json")
        if symbol == "BTC/USD":
            return 200, load("quote_batch.json")["BTC/USD"]
        if symbol == "XAU/USD":
            return 200, load("error_404_plan.json")
        if symbol == "DAX":
            return 200, load("quote_dax_etf.json")
        if symbol.count(",") == 0:
            q = dict(load("quote_eurusd.json"))
            q["symbol"] = symbol
            return 200, q
        return 200, {s: {**load("quote_eurusd.json"), "symbol": s} for s in symbol.split(",")}
    if path == "/time_series":
        interval = request.url.params.get("interval")
        if symbol in ("XAU/USD", "NDX", "DAX"):
            return 200, load("error_404_plan.json")
        if symbol == "BTC/USD":
            return 200, load("error_400_no_data.json")
        return 200, load(
            "time_series_1min_eurusd.json" if interval == "1min" else "time_series_15min_eurusd.json"
        )
    if path == "/symbol_search":
        return 200, load("symbol_search_dax.json" if symbol.lower() == "dax" else "symbol_search_eur.json")
    if path == "/api_usage":
        return 200, load("api_usage.json")
    return 404, {"code": 404, "message": "not found", "status": "error"}


def _refuse(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected Twelve Data call: {request.url.path}")


@pytest.fixture
def prices_env(monkeypatch):
    """Every price test: no network, an instant limiter, and price_symbols restored afterwards."""
    monkeypatch.setattr(service, "TRANSPORT", httpx.MockTransport(_refuse))
    clock = FakeClock()
    monkeypatch.setattr(service, "LIMITER", MinuteLimiter(clock=clock, sleep=clock.sleep))
    with session_factory()() as db:
        saved = {
            s.code: (s.available, s.availability_note, s.checked_at) for s in db.scalars(select(PriceSymbol))
        }
    yield clock
    with session_factory()() as db:
        for s in db.scalars(select(PriceSymbol)):
            s.available, s.availability_note, s.checked_at = saved[s.code]
        db.commit()


def use_twelve_data(monkeypatch, route: Route = default_route) -> TwelveDataMock:
    """Real-provider mode (`price_provider=twelve_data`) through a mock transport."""
    mock = TwelveDataMock(route)
    monkeypatch.setattr(get_settings(), "price_provider", "twelve_data")
    monkeypatch.setattr(service, "TRANSPORT", mock.transport)
    return mock


def give_key(db, user, key: str = KEY) -> None:
    keys_svc.set_key(db, user, "twelve_data", key)
