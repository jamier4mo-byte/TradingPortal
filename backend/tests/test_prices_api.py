"""The /api/prices endpoints (fake provider, as in CI): sign-in, pins, quotes, search, sparkline, settings."""

import pytest
from sqlalchemy import select

from app.models import UserMarketPrefs
from app.services import market_prefs
from tests.conftest import make_client
from tests.test_prices_support import prices_env  # noqa: F401 — fixture

pytestmark = pytest.mark.usefixtures("prices_env")

ENDPOINTS = [
    ("GET", "/api/prices/search?q=eur", None),
    ("GET", "/api/prices/pins", None),
    ("POST", "/api/prices/pins", {"symbol": "EURUSD"}),
    ("DELETE", "/api/prices/pins?symbol=EURUSD", None),
    ("PUT", "/api/prices/pins/order", {"symbols": []}),
    ("GET", "/api/prices/quotes", None),
    ("GET", "/api/prices/quote?symbol=EURUSD", None),
    ("GET", "/api/prices/sparkline?symbol=EURUSD", None),
    ("GET", "/api/prices/usage", None),
    ("PATCH", "/api/prices/settings", {"allow_background_jobs": True}),
]


@pytest.mark.parametrize(("method", "path", "body"), ENDPOINTS)
def test_every_endpoint_needs_sign_in(method, path, body) -> None:
    res = make_client().request(method, path, json=body)
    assert res.status_code == 401


def test_new_users_have_an_empty_watchlist(member_client) -> None:
    body = member_client.get("/api/prices/pins").json()
    assert body == {"pins": [], "max": 8}
    quotes = member_client.get("/api/prices/quotes").json()
    assert quotes["quotes"] == [] and quotes["refresh_seconds"] == 900
    assert quotes["usage"]["provider"] == "fake" and quotes["usage"]["limit"] == 800


def test_pins_cap_order_and_unpin(member_client) -> None:
    codes = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "BTCUSD"]
    for code in codes:
        res = member_client.post("/api/prices/pins", json={"symbol": code})
        assert res.status_code == 201, res.text
    first = member_client.get("/api/prices/pins").json()["pins"][0]
    assert first == {"symbol": "EUR/USD", "code": "EURUSD", "name": "Euro / US dollar", "position": 0}
    again = member_client.post("/api/prices/pins", json={"symbol": "EUR/USD"})  # already pinned: no-op
    assert again.status_code == 201 and again.json()["position"] == 0
    ninth = member_client.post("/api/prices/pins", json={"symbol": "XAUUSD"})
    assert ninth.status_code == 409

    res = member_client.put("/api/prices/pins/order", json={"symbols": ["BTC/USD", "GBPUSD"]})
    order = [p["code"] for p in res.json()["pins"]]
    assert order[:3] == ["BTCUSD", "GBPUSD", "EURUSD"] and len(order) == 8

    assert member_client.delete("/api/prices/pins?symbol=BTC/USD").json() == {"ok": True}
    assert member_client.delete("/api/prices/pins?symbol=BTCUSD").status_code == 404
    assert member_client.post("/api/prices/pins", json={"symbol": "XAUUSD"}).status_code == 201

    quotes = member_client.get("/api/prices/quotes").json()["quotes"]
    assert [q["code"] for q in quotes][0] == "GBPUSD" and len(quotes) == 8
    assert all(q["status"] == "ok" for q in quotes)
    assert member_client.get("/api/prices/usage").json()["used"] == 8  # one batched call, 8 symbols


def test_pins_are_per_user(member_client, admin_client) -> None:
    member_client.post("/api/prices/pins", json={"symbol": "EURUSD"})
    assert admin_client.get("/api/prices/pins").json()["pins"] == []
    assert admin_client.delete("/api/prices/pins?symbol=EURUSD").status_code == 404  # not theirs
    assert len(member_client.get("/api/prices/pins").json()["pins"]) == 1


def test_unknown_provider_symbols_can_be_pinned(member_client) -> None:
    res = member_client.post("/api/prices/pins", json={"symbol": "eth/usd"})
    assert res.status_code == 201 and res.json()["symbol"] == "ETH/USD" and res.json()["code"] is None


def test_bad_symbols_are_refused(member_client) -> None:
    assert member_client.get("/api/prices/quote?symbol=<script>").status_code == 400
    assert member_client.post("/api/prices/pins", json={"symbol": "a" * 40}).status_code == 422


def test_quote_and_fake_mode_states(member_client) -> None:
    eur = member_client.get("/api/prices/quote?symbol=EURUSD").json()
    assert eur["status"] == "ok" and eur["code"] == "EURUSD" and eur["decimals"] == 5
    assert eur["updated_at"] and eur["market_time"]
    ger = member_client.get("/api/prices/quote?symbol=GER40").json()
    assert ger["status"] == "unavailable" and ger["message"] == "Not available on your Twelve Data plan"
    nas = member_client.get("/api/prices/quote?symbol=NAS100").json()
    assert nas["status"] == "ok" and nas["symbol"] == "NDX"


def test_sparkline(member_client) -> None:
    body = member_client.get("/api/prices/sparkline?symbol=XAUUSD").json()
    assert body["status"] == "ok" and body["interval"] == "15min" and 0 < len(body["points"]) <= 96
    assert set(body["points"][0]) == {"t", "v"}


def test_search(member_client) -> None:
    gold = member_client.get("/api/prices/search?q=gold").json()["results"]
    assert gold[0]["code"] == "XAUUSD" and gold[0]["symbol"] == "XAU/USD"
    eur = member_client.get("/api/prices/search?q=eur").json()
    symbols = [r["symbol"] for r in eur["results"]]
    assert "EUR/USD" in symbols and "EUR/GBP" in symbols and symbols.count("EUR/USD") == 1
    assert member_client.get("/api/prices/search?q=eur").json()["cached"] is True


def test_settings_change_only_the_background_fields(member_client, member, db) -> None:
    market_prefs.save_prefs(db, member, instruments=["EURUSD"])
    res = member_client.patch(
        "/api/prices/settings", json={"allow_background_jobs": True, "background_daily_cap": 60}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["allow_background_jobs"] is True and body["background_cap"] == 60
    db.expire_all()
    row = db.scalar(select(UserMarketPrefs))
    assert row.instruments == ["EURUSD"] and row.background_daily_cap == 60
    assert member_client.patch("/api/prices/settings", json={"background_daily_cap": 801}).status_code == 422
    assert member_client.patch("/api/prices/settings", json={"background_daily_cap": -1}).status_code == 422
