"""A deterministic fake price provider for tests, smoke runs, CI and development without a key.

Never shown to a real user as a real price: the service picks it only when `price_provider == "fake"`, or
in `auto` mode in development when neither the user's vault key nor DEV_TWELVE_DATA_KEY exists, and it
keeps the fake's cache entries apart from real ones.

Behaviour:
- Prices are plausible and repeatable: a smooth curve per symbol plus noise seeded by (symbol, 15-minute
  bucket), so a quote moves a little between 15-minute buckets and is identical within one.
- 1-minute and 15-minute bars come from the same curve, so price reactions can be computed in dev.
- Search knows a fixed set of symbols.
- So the dev UI shows every state: `NDX` (Nasdaq 100) is available, but `DAX` (GER40) is refused with
  "Not available on your Twelve Data plan", as Twelve Data refuses indices on individual plans.
- Credits are counted exactly like Twelve Data (1 per symbol / request), so the meter and the daily
  pause can be exercised without a key.
"""

import hashlib
import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from ...models import utcnow
from .provider import (
    UNAVAILABLE_MESSAGE,
    Bar,
    ProviderError,
    Quote,
    Result,
    SearchHit,
    Usage,
)

# provider symbol → (name, exchange, type, base price, decimals, schedule)
SYMBOLS: dict[str, tuple[str, str, str, float, int, str]] = {
    "EUR/USD": ("Euro / US Dollar", "Forex", "Physical Currency", 1.0850, 5, "fx"),
    "GBP/USD": ("British Pound / US Dollar", "Forex", "Physical Currency", 1.2700, 5, "fx"),
    "USD/JPY": ("US Dollar / Japanese Yen", "Forex", "Physical Currency", 150.20, 3, "fx"),
    "USD/CHF": ("US Dollar / Swiss Franc", "Forex", "Physical Currency", 0.8800, 5, "fx"),
    "AUD/USD": ("Australian Dollar / US Dollar", "Forex", "Physical Currency", 0.6550, 5, "fx"),
    "USD/CAD": ("US Dollar / Canadian Dollar", "Forex", "Physical Currency", 1.3700, 5, "fx"),
    "NZD/USD": ("New Zealand Dollar / US Dollar", "Forex", "Physical Currency", 0.5950, 5, "fx"),
    "EUR/GBP": ("Euro / British Pound", "Forex", "Physical Currency", 0.8550, 5, "fx"),
    "GBP/JPY": ("British Pound / Japanese Yen", "Forex", "Physical Currency", 190.80, 3, "fx"),
    "XAU/USD": ("Gold Spot / US Dollar", "Commodity", "Physical Currency", 2650.0, 2, "fx"),
    "BTC/USD": ("Bitcoin US Dollar", "Coinbase Pro", "Digital Currency", 68000.0, 2, "crypto"),
    "ETH/USD": ("Ethereum US Dollar", "Coinbase Pro", "Digital Currency", 2600.0, 2, "crypto"),
    "NDX": ("NASDAQ 100", "NASDAQ", "Index", 20500.0, 2, "index"),
    "AAPL": ("Apple Inc", "NASDAQ", "Common Stock", 225.0, 2, "index"),
}
UNAVAILABLE = {"DAX": ("DAX Performance Index", "XETR", "Index")}


def _unit(*parts: object) -> float:
    """A repeatable number in [-1, 1) from the parts (hashlib, not hash(): stable across processes)."""
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**63 - 1


def _minute(dt: datetime) -> int:
    return int(dt.astimezone(UTC).timestamp() // 60)


def _at(minute: int) -> datetime:
    return datetime.fromtimestamp(minute * 60, UTC)


def level(symbol: str, minute: int) -> float:
    base = SYMBOLS[symbol][3]
    phase = _unit(symbol, "phase") * math.pi
    drift = 0.004 * math.sin(minute / 720 + phase) + 0.0015 * math.sin(minute / 97 + 2 * phase)
    knot, frac = divmod(minute, 15)
    noise = (1 - frac / 15) * _unit(symbol, knot) + (frac / 15) * _unit(symbol, knot + 1)
    return base * (1 + drift + 0.0008 * noise)


def _open_now(schedule: str, now: datetime) -> bool:
    if schedule == "crypto":
        return True
    wd, hour = now.weekday(), now.hour + now.minute / 60
    if schedule == "index":
        return wd < 5 and 14.5 <= hour < 21
    # FX and metals: Sunday 22:00 to Friday 22:00 UTC
    return not (wd == 5 or (wd == 4 and hour >= 22) or (wd == 6 and hour < 22))


class FakePriceProvider:
    name: Literal["fake"] = "fake"

    def __init__(self, clock: Callable[[], datetime] = utcnow) -> None:
        self.clock = clock

    def _r(self, symbol: str, value: float) -> float:
        return round(value, SYMBOLS[symbol][4])

    def _check(self, symbol: str) -> None:
        if symbol in UNAVAILABLE:
            raise ProviderError("plan", UNAVAILABLE_MESSAGE, 404)
        if symbol not in SYMBOLS:
            raise ProviderError("not_found", "Twelve Data doesn't list this symbol", 404)

    def search(self, q: str) -> Result[list[SearchHit]]:
        ql = q.strip().lower()
        hits = [
            SearchHit(symbol=s, name=name, exchange=ex, type=typ, available=True)
            for s, (name, ex, typ, *_rest) in SYMBOLS.items()
            if ql in s.lower() or ql in s.replace("/", "").lower() or ql in name.lower()
        ]
        hits += [
            SearchHit(symbol=s, name=name, exchange=ex, type=typ, available=False)
            for s, (name, ex, typ) in UNAVAILABLE.items()
            if ql in s.lower() or ql in name.lower()
        ]
        return Result(hits[:20], credits=1)

    def _quote(self, symbol: str) -> Quote:
        now = self.clock()
        name, exchange, _typ, _base, dec, schedule = SYMBOLS[symbol]
        bucket = _minute(now) // 15 * 15
        midnight = _minute(now.replace(hour=0, minute=0, second=0, microsecond=0))
        day = [level(symbol, m) for m in range(midnight, bucket + 1, 15)] or [level(symbol, bucket)]
        price, prev = level(symbol, bucket), level(symbol, midnight - 1)
        return Quote(
            symbol=symbol,
            name=name,
            exchange=exchange,
            price=self._r(symbol, price),
            change=self._r(symbol, price - prev),
            percent_change=round((price - prev) / prev * 100, 5),
            open=self._r(symbol, day[0]),
            high=self._r(symbol, max(day)),
            low=self._r(symbol, min(day)),
            previous_close=self._r(symbol, prev),
            is_market_open=_open_now(schedule, now),
            market_time=_at(bucket),
            decimals=dec,
        )

    def quote(self, symbols: list[str]) -> Result[dict[str, Quote | ProviderError]]:
        out: dict[str, Quote | ProviderError] = {}
        for s in symbols:
            key = s.upper()
            try:
                self._check(key)
                out[key] = self._quote(key)
            except ProviderError as exc:
                out[key] = exc
        return Result(out, credits=len(symbols))

    def time_series(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        outputsize: int = 30,
    ) -> Result[list[Bar]]:
        symbol = symbol.upper()
        self._check(symbol)
        step = 15 if interval == "15min" else 1
        last = _minute(min(end, self.clock()) if end else self.clock()) // step * step
        first = _minute(start) // step * step if start else last - step * (outputsize - 1)
        bars: list[Bar] = []
        for m in range(first, last + 1, step):
            o, c = level(symbol, m), level(symbol, m + step)
            wiggle = abs(_unit(symbol, "w", m)) * SYMBOLS[symbol][3] * 0.0002
            bars.append(
                Bar(
                    t=_at(m),
                    open=self._r(symbol, o),
                    high=self._r(symbol, max(o, c) + wiggle),
                    low=self._r(symbol, min(o, c) - wiggle),
                    close=self._r(symbol, c),
                )
            )
        return Result(bars[-outputsize:], credits=1)

    def usage(self) -> Result[Usage]:
        # The fake has no server-side counter; the service reports its own.
        return Result(Usage(used_today=None, daily_limit=800, plan="Basic (fake)"), credits=1)
