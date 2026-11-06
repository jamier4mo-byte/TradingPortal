"""Prices for the Hub (F1, F13): quotes, sparklines, search, pins, the credit meter and settings.

Which provider a request uses (never a fake price for a real user):
- `price_provider == "fake"`: the fake, always (tests, smoke, CI).
- otherwise the user's own vault key; else, in development only, DEV_TWELVE_DATA_KEY; else, in
  development with `auto`, the fake; else (production, no key) nothing: status `no_key`.

Caching: one cache in `price_cache` keyed by symbol and shared by everyone (credits are charged to
whoever's key fetched): quote and sparkline 15 minutes, search 24 hours, reaction series for good.
`SHARED_CACHE = False` turns it into a per-user cache (Twelve Data's Basic plan is "internal non-display";
the shared cache is what Prompt 4 asks for, flagged for Jamie). The fake's entries are kept apart so a
fake price can never be served to someone using a real key.

Every real call queues on the per-key minute limiter and is charged to the user's daily counter; at 800
credits the user is paused and sees the last cached values marked `stale`.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.settings import get_settings
from ...models import Instrument, PriceCache, PricePin, PriceSymbol, User, utcnow
from .. import keys as keys_svc
from .. import market_prefs
from . import credits as credits_svc
from .fake import FakePriceProvider
from .limiter import MinuteLimiter
from .provider import (
    DAILY_LIMIT_MESSAGE,
    UNAVAILABLE_MESSAGE,
    PriceProvider,
    ProviderError,
    Quote,
    Result,
    SearchHit,
    TwelveDataProvider,
)

SHARED_CACHE = True  # one-line switch to a per-user cache (see the module docstring)
MAX_PINS = 8
REFRESH_SECONDS = 900
TTL = {
    "quote": timedelta(minutes=15),
    "sparkline": timedelta(minutes=15),
    "search": timedelta(hours=24),
}
TTL_UNAVAILABLE = timedelta(hours=24)  # a plan refusal won't change within the day
SPARK_INTERVAL = "15min"
SPARK_POINTS = 96  # about the last 24 hours, one credit
NO_KEY_MESSAGE = "Add your Twelve Data key in Settings to see live prices"
SEARCH_MIN_PROVIDER_CHARS = 2
SYMBOL_RE = re.compile(r"^[A-Z0-9/.:_\- ]{1,32}$")
SUBSTITUTE_WORDS = ("etf", "fund", "trust", "shares", "ishares")

# Tests swap these: an httpx.MockTransport (never the network), a limiter with a fake clock and sleep.
TRANSPORT: httpx.BaseTransport | None = None
LIMITER = MinuteLimiter()


class PriceError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def make_twelve_data(api_key: str) -> TwelveDataProvider:
    return TwelveDataProvider(api_key, transport=TRANSPORT)


def provider_for_key(api_key: str, now: datetime | None = None) -> PriceProvider:
    """The provider the vault's "Check key" uses: the fake only in fake mode (tests, smoke, CI)."""
    if get_settings().price_provider == "fake":
        return FakePriceProvider(clock=_clock(now))
    return make_twelve_data(api_key)


def _clock(now: datetime | None) -> Callable[[], datetime]:
    return (lambda: now) if now else utcnow


# ---- which provider, whose key ---------------------------------------------------------------------


@dataclass
class Account:
    user_id: int
    provider: PriceProvider | None
    source: Literal["twelve_data", "fake"]
    has_key: bool
    limiter_key: str | None  # None: no per-minute limit (the fake)

    @property
    def fake(self) -> bool:
        return self.source == "fake"


def _vault_key(db: Session, user: User) -> str | None:
    try:
        return keys_svc.reveal_for_server_use(db, user, "twelve_data")
    except Exception:  # noqa: BLE001 — an unreadable key is treated as no key (never logged)
        return None


def account_for(db: Session, user: User, now: datetime | None = None) -> Account:
    s = get_settings()
    fake = Account(user.id, FakePriceProvider(clock=_clock(now)), "fake", False, None)
    if s.price_provider == "fake":
        return fake
    key = _vault_key(db, user)
    if key:
        return Account(user.id, make_twelve_data(key), "twelve_data", True, f"user:{user.id}")
    if s.env == "development" and s.dev_twelve_data_key:
        return Account(user.id, make_twelve_data(s.dev_twelve_data_key), "twelve_data", True, "dev")
    if s.price_provider == "auto" and s.env == "development":
        return fake
    return Account(user.id, None, "twelve_data", False, None)


def spend[T](
    db: Session,
    acct: Account,
    credits: int,
    call: Callable[[], Result[T]],
    now: datetime,
    *,
    background: bool = False,
    block: bool = True,
) -> Result[T]:
    """Queue on the minute limiter, make the call, charge the credits to the user whose key fetched."""
    if acct.limiter_key and LIMITER.acquire(acct.limiter_key, credits, block=block) is None:
        raise ProviderError("minute_limit", "Per-minute limit full")
    try:
        result = call()
    except ProviderError as exc:
        if exc.kind == "daily_limit":
            credits_svc.mark_exhausted(db, acct.user_id, now)
        elif exc.kind == "minute_limit" and acct.limiter_key:
            LIMITER.note_left(acct.limiter_key, 0)
        raise
    credits_svc.charge(db, acct.user_id, result.credits, now, background=background)
    if acct.limiter_key:
        LIMITER.note_left(acct.limiter_key, result.minute_left)
    return result


# ---- symbols ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Resolved:
    symbol: str  # the provider's, e.g. XAU/USD
    code: str | None  # ours, e.g. XAUUSD
    name: str | None
    unit: str | None
    decimals: int | None
    pip_size: float | None
    asset_class: str | None


def clean_symbol(raw: str) -> str:
    s = (raw or "").strip().upper()
    if not SYMBOL_RE.match(s):
        raise PriceError("That isn't a symbol we can look up.")
    return s


def resolve(db: Session, raw: str) -> Resolved:
    """Our code (XAUUSD) or a provider symbol (XAU/USD, AAPL) → both."""
    s = clean_symbol(raw)
    row = db.scalar(select(PriceSymbol).where(PriceSymbol.code == s)) or db.scalar(
        select(PriceSymbol).where(PriceSymbol.provider_symbol == s)
    )
    if row is None:
        return Resolved(s, None, None, None, None, None, None)
    decimals = db.scalar(select(Instrument.price_decimals).where(Instrument.symbol == row.code))
    return Resolved(
        row.provider_symbol, row.code, row.name, row.unit, decimals, row.pip_size, row.asset_class
    )


def record_availability(db: Session, r: Resolved, available: bool, now: datetime) -> None:
    """A real answer from Twelve Data: remember whether the plan has this symbol."""
    if r.code is None:
        return
    row = db.scalar(select(PriceSymbol).where(PriceSymbol.code == r.code))
    if row is None:
        return
    row.available = available
    row.availability_note = None if available else UNAVAILABLE_MESSAGE
    row.checked_at = now
    db.commit()


def _is_substitute(r: Resolved, q: Quote) -> bool:
    """Twelve Data answers "DAX" with a US-listed ETF. Never show an ETF as the index."""
    if r.asset_class != "index":
        return False
    words = (q.name or "").lower().replace(",", " ").replace(".", " ").split()
    return any(word in words for word in SUBSTITUTE_WORDS)


# ---- cache ----------------------------------------------------------------------------------------


def cache_key(acct: Account, key: str) -> str:
    prefix = "fake:" if acct.fake else ""
    if not SHARED_CACHE:
        prefix += f"u{acct.user_id}:"
    return (prefix + key)[:120]


def cache_get(db: Session, kind: str, key: str) -> PriceCache | None:
    return db.scalar(select(PriceCache).where(PriceCache.kind == kind, PriceCache.key == key))


def cache_put(
    db: Session,
    kind: str,
    key: str,
    *,
    now: datetime,
    user_id: int | None,
    payload: dict | list | None = None,
    status: str = "ok",
    message: str | None = None,
) -> PriceCache:
    row = cache_get(db, kind, key)
    if row is None:
        row = PriceCache(kind=kind, key=key)
        db.add(row)
    row.status, row.payload, row.message = status, payload, message
    row.fetched_at, row.fetched_by_user_id = now, user_id
    db.commit()
    return row


def fresh(row: PriceCache | None, kind: str, now: datetime) -> bool:
    if row is None:
        return False
    if kind == "series":
        return True
    ttl = TTL_UNAVAILABLE if row.status == "unavailable" else TTL[kind]
    return row.fetched_at > now - ttl


# ---- quotes ---------------------------------------------------------------------------------------


def _quote_out(
    r: Resolved,
    status: str,
    q: Quote | None = None,
    updated_at: datetime | None = None,
    message: str | None = None,
) -> dict:
    return {
        "symbol": r.symbol,
        "code": r.code,
        "name": r.name or (q.name if q else None) or r.symbol,
        "unit": r.unit,
        "decimals": r.decimals if r.decimals is not None else (q.decimals if q else None),
        "status": status,
        "price": q.price if q else None,
        "change": q.change if q else None,
        "percent_change": q.percent_change if q else None,
        "open": q.open if q else None,
        "high": q.high if q else None,
        "low": q.low if q else None,
        "previous_close": q.previous_close if q else None,
        "is_market_open": q.is_market_open if q else None,
        "market_time": q.market_time if q else None,
        "updated_at": updated_at,
        "message": message,
    }


def _from_cache(r: Resolved, row: PriceCache, status: str | None = None, message: str | None = None) -> dict:
    q = Quote.from_payload(row.payload) if row.status == "ok" and isinstance(row.payload, dict) else None
    st = status or ("ok" if row.status == "ok" else row.status)
    return _quote_out(r, st, q, row.fetched_at, message if message is not None else row.message)


def _fallback(r: Resolved, row: PriceCache | None, message: str) -> dict:
    """The provider can't answer now: the last known price marked stale, or an error."""
    if row is not None and row.status == "ok":
        return _from_cache(r, row, "stale", message)
    if row is not None and row.status == "unavailable":
        return _from_cache(r, row)
    return _quote_out(r, "stale" if message == DAILY_LIMIT_MESSAGE else "error", message=message)


def get_quotes(db: Session, user: User, symbols: list[str], now: datetime | None = None) -> list[dict]:
    """Quotes for these symbols: fresh cache first, then one batched call for the rest."""
    now = now or utcnow()
    acct = account_for(db, user, now)
    resolved = [resolve(db, s) for s in symbols]
    if acct.provider is None:
        return [_quote_out(r, "no_key", message=NO_KEY_MESSAGE) for r in resolved]

    out: dict[str, dict] = {}
    stale: dict[str, tuple[Resolved, PriceCache | None]] = {}
    for r in resolved:
        row = cache_get(db, "quote", cache_key(acct, r.symbol))
        if fresh(row, "quote", now):
            out[r.symbol] = _from_cache(r, row)  # type: ignore[arg-type]
        else:
            stale[r.symbol] = (r, row)

    if stale and credits_svc.paused(db, user.id, now):
        for sym, (r, row) in stale.items():
            out[sym] = _fallback(r, row, DAILY_LIMIT_MESSAGE)
    elif stale:
        provider = acct.provider
        wanted = list(stale)
        try:
            result = spend(db, acct, len(wanted), lambda: provider.quote(wanted), now)
        except ProviderError as exc:
            for sym, (r, row) in stale.items():
                if len(stale) == 1 and exc.kind in ("plan", "not_found"):
                    # one symbol: Twelve Data answers its refusal as the whole body
                    out[sym] = _store_quote(db, acct, r, row, exc, now)
                else:
                    out[sym] = _fallback(r, row, exc.message)
        else:
            for sym, (r, row) in stale.items():
                out[sym] = _store_quote(db, acct, r, row, result.data.get(sym.upper()), now)
    return [out[r.symbol] for r in resolved]


def _store_quote(
    db: Session,
    acct: Account,
    r: Resolved,
    row: PriceCache | None,
    item: Quote | ProviderError | None,
    now: datetime,
) -> dict:
    key = cache_key(acct, r.symbol)
    if isinstance(item, Quote) and _is_substitute(r, item):
        item = ProviderError("plan", UNAVAILABLE_MESSAGE)
    if isinstance(item, Quote):
        if not acct.fake:
            record_availability(db, r, True, now)
        cached = cache_put(db, "quote", key, now=now, user_id=acct.user_id, payload=item.to_payload())
        return _from_cache(r, cached)
    if isinstance(item, ProviderError) and item.kind in ("plan", "not_found"):
        if item.kind == "plan" and not acct.fake:
            record_availability(db, r, False, now)
        cached = cache_put(
            db, "quote", key, now=now, user_id=acct.user_id, status="unavailable", message=item.message
        )
        return _from_cache(r, cached)
    return _fallback(r, row, item.message if item else "Twelve Data didn't return this symbol")


def get_quote(db: Session, user: User, symbol: str, now: datetime | None = None) -> dict:
    return get_quotes(db, user, [symbol], now)[0]


# ---- sparkline ------------------------------------------------------------------------------------


def _spark_out(r: Resolved, status: str, row: PriceCache | None = None, message: str | None = None) -> dict:
    points = row.payload if row is not None and row.status == "ok" and isinstance(row.payload, list) else []
    return {
        "symbol": r.symbol,
        "code": r.code,
        "status": status,
        "interval": SPARK_INTERVAL,
        "points": [{"t": t, "v": v} for t, v in points],
        "updated_at": row.fetched_at if row is not None else None,
        "message": message if message is not None else (row.message if row is not None else None),
    }


def get_sparkline(db: Session, user: User, symbol: str, now: datetime | None = None) -> dict:
    """Intraday 15-minute closes for about the last 24 hours (one credit, cached 15 minutes)."""
    now = now or utcnow()
    r = resolve(db, symbol)
    acct = account_for(db, user, now)
    if acct.provider is None:
        return _spark_out(r, "no_key", message=NO_KEY_MESSAGE)
    key = cache_key(acct, r.symbol)
    row = cache_get(db, "sparkline", key)
    if fresh(row, "sparkline", now):
        return _spark_out(r, row.status, row)  # type: ignore[union-attr]

    def fallback(message: str) -> dict:
        if row is not None and row.status == "ok":
            return _spark_out(r, "stale", row, message)
        return _spark_out(r, "stale" if message == DAILY_LIMIT_MESSAGE else "error", message=message)

    if credits_svc.paused(db, user.id, now):
        return fallback(DAILY_LIMIT_MESSAGE)
    provider = acct.provider
    try:
        result = spend(
            db, acct, 1, lambda: provider.time_series(r.symbol, SPARK_INTERVAL, outputsize=SPARK_POINTS), now
        )
    except ProviderError as exc:
        if exc.kind in ("plan", "not_found"):
            if exc.kind == "plan" and not acct.fake:
                record_availability(db, r, False, now)
            row = cache_put(
                db, "sparkline", key, now=now, user_id=acct.user_id, status="unavailable", message=exc.message
            )
            return _spark_out(r, "unavailable", row)
        return fallback(exc.message)
    points = [[b.t.isoformat(), b.close] for b in result.data]
    row = cache_put(db, "sparkline", key, now=now, user_id=acct.user_id, payload=points)
    return _spark_out(r, "ok", row)


# ---- search -------------------------------------------------------------------------------------


def _local_hits(db: Session, ql: str) -> list[dict]:
    out = []
    for row in db.scalars(select(PriceSymbol).order_by(PriceSymbol.id)):
        if ql in row.code.lower() or ql in row.provider_symbol.lower() or ql in row.name.lower():
            out.append(
                {
                    "symbol": row.provider_symbol,
                    "code": row.code,
                    "name": row.name,
                    "exchange": None,
                    "type": row.asset_class,
                    "available": row.available,
                }
            )
    return out


def _merge(db: Session, local: list[dict], hits: list[dict]) -> list[dict]:
    codes = {row.provider_symbol: row for row in db.scalars(select(PriceSymbol))}
    seen = {h["symbol"] for h in local}
    out = list(local)
    for h in hits:
        row = codes.get(h["symbol"])
        # "DAX" in Twelve Data's search is a US-listed ETF: never label it as our GER40 index.
        code = row.code if row and (row.asset_class != "index" or (h.get("type") or "") == "Index") else None
        if code and h["symbol"] in seen:
            continue
        out.append({**h, "code": code})
    return out[:20]


def search(db: Session, user: User, q: str, now: datetime | None = None) -> dict:
    now = now or utcnow()
    q = q.strip()
    ql = q.lower()
    local = _local_hits(db, ql)
    acct = account_for(db, user, now)
    if acct.provider is None or len(q) < SEARCH_MIN_PROVIDER_CHARS:
        return {"results": local[:20], "cached": False}
    key = cache_key(acct, ql)
    row = cache_get(db, "search", key)
    if fresh(row, "search", now):
        return {"results": _merge(db, local, row.payload or []), "cached": True}  # type: ignore[union-attr]
    if credits_svc.paused(db, user.id, now):
        return {"results": _merge(db, local, row.payload if row else []), "cached": row is not None}
    provider = acct.provider
    try:
        result = spend(db, acct, 1, lambda: provider.search(q), now)
    except ProviderError:
        return {"results": _merge(db, local, row.payload if row else []), "cached": row is not None}
    hits = [_hit_dict(h) for h in result.data]
    cache_put(db, "search", key, now=now, user_id=acct.user_id, payload=hits)
    return {"results": _merge(db, local, hits), "cached": False}


def _hit_dict(h: SearchHit) -> dict:
    return {
        "symbol": h.symbol,
        "name": h.name,
        "exchange": h.exchange,
        "type": h.type,
        "available": h.available,
    }


# ---- pins ---------------------------------------------------------------------------------------


def _pins(db: Session, user: User) -> list[PricePin]:
    return list(
        db.scalars(
            select(PricePin).where(PricePin.user_id == user.id).order_by(PricePin.position, PricePin.id)
        )
    )


def _pin_out(db: Session, pin: PricePin) -> dict:
    r = resolve(db, pin.symbol)
    return {"symbol": r.symbol, "code": r.code, "name": r.name or r.symbol, "position": pin.position}


def list_pins(db: Session, user: User) -> list[dict]:
    return [_pin_out(db, p) for p in _pins(db, user)]


def _stored(r: Resolved) -> str:
    return r.code or r.symbol


def add_pin(db: Session, user: User, symbol: str) -> dict:
    r = resolve(db, symbol)
    existing = {p.symbol: p for p in _pins(db, user)}
    if _stored(r) in existing:
        return _pin_out(db, existing[_stored(r)])
    if len(existing) >= MAX_PINS:
        raise PriceError(f"You can pin up to {MAX_PINS} instruments. Unpin one first.", 409)
    top = db.scalar(select(func.max(PricePin.position)).where(PricePin.user_id == user.id))
    pin = PricePin(user_id=user.id, symbol=_stored(r), position=(top + 1) if top is not None else 0)
    db.add(pin)
    db.commit()
    return _pin_out(db, pin)


def remove_pin(db: Session, user: User, symbol: str) -> None:
    r = resolve(db, symbol)
    pin = db.scalar(
        select(PricePin).where(PricePin.user_id == user.id, PricePin.symbol.in_({_stored(r), r.symbol}))
    )
    if pin is None:
        raise PriceError("That instrument isn't pinned.", 404)
    db.delete(pin)
    db.commit()


def reorder_pins(db: Session, user: User, symbols: list[str]) -> list[dict]:
    """Pins in the given order first; any not named keep their order after them."""
    pins = _pins(db, user)
    by_symbol = {p.symbol: p for p in pins}
    ordered: list[PricePin] = []
    for s in symbols:
        r = resolve(db, s)
        pin = by_symbol.get(_stored(r)) or by_symbol.get(r.symbol)
        if pin is not None and pin not in ordered:
            ordered.append(pin)
    ordered += [p for p in pins if p not in ordered]
    for i, pin in enumerate(ordered):
        pin.position = i
    db.commit()
    return list_pins(db, user)


def pinned_quotes(db: Session, user: User, now: datetime | None = None) -> list[dict]:
    symbols = [p.symbol for p in _pins(db, user)]
    return get_quotes(db, user, symbols, now) if symbols else []


# ---- usage and settings -------------------------------------------------------------------------


def usage(db: Session, user: User, now: datetime | None = None) -> dict:
    now = now or utcnow()
    acct = account_for(db, user, now)
    prefs = market_prefs.get_prefs(db, user)
    used = credits_svc.used(db, user.id, now)
    paused = acct.provider is not None and used >= credits_svc.DAILY_LIMIT
    return {
        "provider": acct.source,
        "has_key": acct.has_key,
        "used": used,
        "limit": credits_svc.DAILY_LIMIT,
        "background_used": credits_svc.background_used(db, user.id, now),
        "background_cap": prefs.background_daily_cap,
        "allow_background_jobs": prefs.allow_background_jobs,
        "resets_at": credits_svc.resets_at(now),
        "paused": paused,
        "paused_reason": credits_svc.PAUSED_REASON if paused else None,
    }


def update_settings(
    db: Session,
    user: User,
    *,
    allow_background_jobs: bool | None = None,
    background_daily_cap: int | None = None,
    now: datetime | None = None,
) -> dict:
    market_prefs.save_prefs(
        db, user, allow_background_jobs=allow_background_jobs, background_daily_cap=background_daily_cap
    )
    return usage(db, user, now)


# ---- the vault's "Check key" ----------------------------------------------------------------------


def check_key(db: Session, user: User, api_key: str, now: datetime | None = None) -> tuple[bool | None, str]:
    """Call `/api_usage` (1 credit, counted).

    Returns (True, "Key works · …"), (False, "Twelve Data rejected this key") or (None, message) when
    Twelve Data couldn't answer, in which case the stored test result is left alone.
    """
    now = now or utcnow()
    provider = provider_for_key(api_key, now)
    acct = Account(
        user.id,
        provider,
        provider.name,
        True,
        None if provider.name == "fake" else f"user:{user.id}",
    )
    try:
        result = spend(db, acct, 1, provider.usage, now)
    except ProviderError as exc:
        if exc.kind == "invalid_key":
            return False, "Twelve Data rejected this key"
        if exc.kind == "daily_limit":
            return True, "Key works · daily limit reached (resets at 00:00 UTC)"
        if exc.kind == "minute_limit":
            return None, "Twelve Data's per-minute limit is full – try again in a minute"
        return None, "Couldn't reach Twelve Data – try again"
    used = credits_svc.record_reported(db, user.id, result.data.used_today, now)
    limit = result.data.daily_limit or credits_svc.DAILY_LIMIT
    return True, f"Key works · {used} of {limit} credits used today"
