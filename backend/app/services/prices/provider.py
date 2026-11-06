"""The swappable price provider (F1): typed results, the errors we branch on, and Twelve Data.

Every provider method returns a `Result` holding the parsed data and the credits the call cost, so the
service can charge the user whose key fetched it. Twelve Data facts (researched 6 Nov 2026):

- `/quote`, `/price`, `/time_series` cost 1 credit per symbol; `/symbol_search` 1 per request; `/api_usage` 1.
- Errors come as `{"code": 4xx, "message": ..., "status": "error"}`, sometimes with HTTP 200, so any body
  with `status == "error"` is an error and we branch on its `code`.
- The key goes in the `Authorization: apikey <key>` header, never the URL, so it can't leak through URL
  logs or exception messages.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

import httpx

from ..http import client

BASE_URL = "https://api.twelvedata.com"
UNAVAILABLE_MESSAGE = "Not available on your Twelve Data plan"
NOT_FOUND_MESSAGE = "Twelve Data doesn't list this symbol"
REJECTED_MESSAGE = "Twelve Data rejected this key"
UNREACHABLE_MESSAGE = "Couldn't reach Twelve Data – try again shortly"
BUSY_MESSAGE = "Twelve Data's per-minute limit is full – try again in a minute"
DAILY_LIMIT_MESSAGE = "Live data paused – daily limit reached"

ErrorKind = Literal["invalid_key", "plan", "not_found", "minute_limit", "daily_limit", "error"]


class ProviderError(Exception):
    """A provider refusal. `message` is safe to show; it never holds the key."""

    def __init__(self, kind: ErrorKind, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.code = code


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str | None = None
    exchange: str | None = None
    price: float | None = None
    change: float | None = None
    percent_change: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
    is_market_open: bool | None = None
    market_time: datetime | None = None
    decimals: int | None = None  # from the provider's price string, for symbols we don't know

    def to_payload(self) -> dict:
        out = asdict(self)
        out["market_time"] = self.market_time.isoformat() if self.market_time else None
        return out

    @classmethod
    def from_payload(cls, data: dict) -> "Quote":
        data = dict(data)
        mt = data.get("market_time")
        data["market_time"] = datetime.fromisoformat(mt) if mt else None
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass(frozen=True)
class Bar:
    t: datetime  # bar start, UTC
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class SearchHit:
    symbol: str
    name: str
    exchange: str | None = None
    type: str | None = None
    country: str | None = None
    currency: str | None = None
    available: bool | None = None  # on the Basic (free) plan


@dataclass(frozen=True)
class Usage:
    used_today: int | None  # daily_usage
    daily_limit: int | None  # plan_daily_limit
    minute_used: int | None = None
    minute_limit: int | None = None
    plan: str | None = None


@dataclass
class Result[T]:
    data: T
    credits: int
    minute_left: int | None = None  # the `api-credits-left` header: credits left this minute


class PriceProvider(Protocol):
    name: Literal["twelve_data", "fake"]

    def search(self, q: str) -> Result[list[SearchHit]]: ...

    def quote(self, symbols: list[str]) -> Result[dict[str, Quote | ProviderError]]: ...

    def time_series(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        outputsize: int = 30,
    ) -> Result[list[Bar]]: ...

    def usage(self) -> Result[Usage]: ...


# ---- parsing (shared with the fake and the tests) -------------------------------------------------


def num(value: Any) -> float | None:
    """Twelve Data sends prices as strings. "" / None / junk → None."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def decimals_of(value: Any) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    return len(value.split(".", 1)[1]) if "." in value else 0


def parse_time(value: Any) -> datetime | None:
    """ "2026-11-06 13:30:00" or "2026-11-06" (we always ask for timezone=UTC) → aware UTC."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def classify(code: int | None, message: str | None) -> ProviderError:
    m = (message or "").lower()
    if code == 401:
        return ProviderError("invalid_key", REJECTED_MESSAGE, code)
    if code == 403 or (code == 404 and ("plan" in m or "pricing" in m)):
        return ProviderError("plan", UNAVAILABLE_MESSAGE, code)
    if code == 404:
        return ProviderError("not_found", NOT_FOUND_MESSAGE, code)
    if code == 429:
        if "for the day" in m or "daily" in m:
            return ProviderError("daily_limit", DAILY_LIMIT_MESSAGE, code)
        return ProviderError("minute_limit", BUSY_MESSAGE, code)
    return ProviderError("error", f"Twelve Data answered with an error ({code or 'unknown'})", code)


def _is_no_data(body: dict) -> bool:
    return body.get("code") == 400 and "no data" in str(body.get("message", "")).lower()


def parse_quote(item: dict) -> Quote:
    ts = item.get("timestamp")
    market_time = datetime.fromtimestamp(int(ts), UTC) if isinstance(ts, int | float) else None
    return Quote(
        symbol=str(item.get("symbol", "")).upper(),
        name=item.get("name") or None,
        exchange=item.get("exchange") or None,
        price=num(item.get("close")),
        change=num(item.get("change")),
        percent_change=num(item.get("percent_change")),
        open=num(item.get("open")),
        high=num(item.get("high")),
        low=num(item.get("low")),
        previous_close=num(item.get("previous_close")),
        is_market_open=item.get("is_market_open") if isinstance(item.get("is_market_open"), bool) else None,
        market_time=market_time or parse_time(item.get("datetime")),
        decimals=decimals_of(item.get("close")),
    )


def parse_quotes(body: dict, symbols: list[str]) -> dict[str, Quote | ProviderError]:
    """One symbol → a flat quote; several → `{symbol: quote-or-error}`. Keys are upper-cased."""
    if isinstance(body.get("symbol"), str):
        items = {symbols[0] if len(symbols) == 1 else body["symbol"]: body}
    else:
        items = {k: v for k, v in body.items() if isinstance(v, dict)}
    out: dict[str, Quote | ProviderError] = {}
    for key, item in items.items():
        if item.get("status") == "error":
            out[key.upper()] = classify(item.get("code"), item.get("message"))
        else:
            out[key.upper()] = parse_quote(item)
    return out


def parse_series(body: dict) -> list[Bar]:
    bars: list[Bar] = []
    for v in body.get("values") or []:
        t = parse_time(v.get("datetime"))
        o, h, low, c = num(v.get("open")), num(v.get("high")), num(v.get("low")), num(v.get("close"))
        if t is None or None in (o, h, low, c):
            continue
        bars.append(Bar(t=t, open=o, high=h, low=low, close=c))  # type: ignore[arg-type]
    return sorted(bars, key=lambda b: b.t)


def parse_search(body: dict) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for item in body.get("data") or []:
        access = item.get("access") or {}
        plan = access.get("plan") if isinstance(access, dict) else None
        hits.append(
            SearchHit(
                symbol=str(item.get("symbol", "")).upper(),
                name=item.get("instrument_name") or item.get("symbol") or "",
                exchange=item.get("exchange") or None,
                type=item.get("instrument_type") or None,
                country=item.get("country") or None,
                currency=item.get("currency") or None,
                available=None if not plan else plan == "Basic",
            )
        )
    return hits


def parse_usage(body: dict) -> Usage:
    def _int(v: Any) -> int | None:
        return int(v) if isinstance(v, int | float) or (isinstance(v, str) and v.isdigit()) else None

    return Usage(
        used_today=_int(body.get("daily_usage")),
        daily_limit=_int(body.get("plan_daily_limit")),
        minute_used=_int(body.get("current_usage")),
        minute_limit=_int(body.get("plan_limit")),
        plan=body.get("plan_category") or None,
    )


def fmt_time(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


# ---- Twelve Data -------------------------------------------------------------------------------


class TwelveDataProvider:
    """Twelve Data over HTTPS. Pass `transport` (httpx.MockTransport) in tests; tests never call out."""

    name: Literal["twelve_data"] = "twelve_data"

    def __init__(self, api_key: str, transport: httpx.BaseTransport | None = None) -> None:
        self.__key = api_key
        self._transport = transport

    def __repr__(self) -> str:  # never show the key
        return "TwelveDataProvider(key=***)"

    def _scrub(self, text: str) -> str:
        return text.replace(self.__key, "***") if self.__key else text

    def _get(self, path: str, params: dict) -> tuple[Any, int | None]:
        try:
            with client(
                transport=self._transport,
                base_url=BASE_URL,
                headers={"Authorization": f"apikey {self.__key}"},
            ) as c:
                res = c.get(path, params=params)
        except httpx.HTTPError:
            raise ProviderError("error", UNREACHABLE_MESSAGE) from None
        left = res.headers.get("api-credits-left")
        minute_left = int(left) if left and left.lstrip("-").isdigit() else None
        try:
            body = res.json()
        except ValueError:
            raise ProviderError("error", f"Twelve Data answered {res.status_code}", res.status_code) from None
        if isinstance(body, dict) and body.get("status") == "error":
            if _is_no_data(body):
                return {"values": [], "status": "ok"}, minute_left
            err = classify(body.get("code") or res.status_code, self._scrub(str(body.get("message", ""))))
            raise err
        if res.status_code >= 400:
            raise classify(res.status_code, "")
        return body, minute_left

    def search(self, q: str) -> Result[list[SearchHit]]:
        body, left = self._get("/symbol_search", {"symbol": q, "outputsize": 20, "show_plan": "true"})
        return Result(parse_search(body), credits=1, minute_left=left)

    def quote(self, symbols: list[str]) -> Result[dict[str, Quote | ProviderError]]:
        body, left = self._get("/quote", {"symbol": ",".join(symbols)})
        return Result(
            parse_quotes(body, [s.upper() for s in symbols]), credits=len(symbols), minute_left=left
        )

    def time_series(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        outputsize: int = 30,
    ) -> Result[list[Bar]]:
        params: dict = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "timezone": "UTC",
            "order": "asc",
        }
        if start:
            params["start_date"] = fmt_time(start)
        if end:
            params["end_date"] = fmt_time(end)
        body, left = self._get("/time_series", params)
        return Result(parse_series(body), credits=1, minute_left=left)

    def usage(self) -> Result[Usage]:
        body, left = self._get("/api_usage", {})
        return Result(parse_usage(body), credits=1, minute_left=left)


ProviderFactory = Callable[[str], PriceProvider]
