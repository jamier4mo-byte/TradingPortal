"""Price reactions after high-impact releases (Foundations 3.3), computed once and stored.

The scheduler calls `run(db, now)` every minute. For each high-impact event released between 7 days and
65 minutes ago, and each instrument its currency moves (`news_instrument_map`), one 1-minute series
covering [release, release + 60 min] (1 credit) gives rows for the 5, 15 and 60 minutes after:
open = the first bar's open at or after the release, high/low over the horizon, close at its end,
`range_units` = (high − low) / pip size and `move_units` = (close − open) / pip size, in the instrument's
pips or points; direction is flat when the move is under one unit.

Credits come only from users who opted in (`allow_background_jobs`), only from leftovers: each user's
background spend is capped by `background_daily_cap` per UTC day, and background work never takes a
user's day above 800 − RESERVE, keeping RESERVE credits for their watchlist and search. Users take turns
(a cursor in app_state), at most MAX_SERIES_PER_TICK series per tick, and a full minute window is
skipped rather than waited for. The credit is charged to the user whose key fetched.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models import AppState, Event, PriceReaction, PriceSymbol, User, UserMarketPrefs, utcnow
from .. import market_prefs
from . import credits as credits_svc
from . import service
from .provider import Bar, ProviderError

HORIZONS = (5, 15, 60)
SETTLE = timedelta(minutes=65)
LOOKBACK = timedelta(days=7)
RESERVE = 200  # kept for the watchlist and search
MAX_SERIES_PER_TICK = 5
CURSOR_KEY = "prices.reactions.cursor"
SERIES_INTERVAL = "1min"
SERIES_OUTPUTSIZE = 90  # 61 one-minute bars, with room to spare


@dataclass(frozen=True)
class Horizon:
    status: str  # ok | no_data | unavailable
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    range_units: float | None = None
    move_units: float | None = None
    direction: str | None = None


def compute(bars: list[Bar], release: datetime, pip_size: float) -> dict[int, Horizon]:
    """The 5/15/60-minute reaction from 1-minute bars. A bar starting at t covers [t, t + 1 min)."""
    after = sorted((b for b in bars if b.t >= release), key=lambda b: b.t)
    out: dict[int, Horizon] = {}
    for h in HORIZONS:
        window = [b for b in after if b.t < release + timedelta(minutes=h)]
        if not window:
            out[h] = Horizon("no_data")
            continue
        o, c = window[0].open, window[-1].close
        hi, lo = max(b.high for b in window), min(b.low for b in window)
        move = round((c - o) / pip_size, 1)
        out[h] = Horizon(
            status="ok",
            open=o,
            high=hi,
            low=lo,
            close=c,
            range_units=round((hi - lo) / pip_size, 1),
            move_units=move,
            direction="flat" if abs(move) < 1 else ("up" if move > 0 else "down"),
        )
    return out


def allowance(db: Session, user_id: int, prefs: UserMarketPrefs, now: datetime) -> int:
    """Credits this user's key may still spend in the background today."""
    used = credits_svc.used(db, user_id, now)
    bg = credits_svc.background_used(db, user_id, now)
    return max(0, min(prefs.background_daily_cap - bg, credits_svc.DAILY_LIMIT - RESERVE - used))


def _opted_in(db: Session) -> list[tuple[User, UserMarketPrefs]]:
    rows = db.execute(
        select(User, UserMarketPrefs)
        .join(UserMarketPrefs, UserMarketPrefs.user_id == User.id)
        .where(UserMarketPrefs.allow_background_jobs.is_(True))
        .order_by(User.id)
    ).all()
    return [(u, p) for u, p in rows if u.is_active]


def _pending(db: Session, now: datetime) -> list[tuple[Event, PriceSymbol]]:
    events = list(
        db.scalars(
            select(Event)
            .where(
                Event.impact == "high",
                Event.all_day.is_(False),
                Event.at <= now - SETTLE,
                Event.at >= now - LOOKBACK,
            )
            .order_by(Event.at.desc(), Event.id)
        )
    )
    if not events:
        return []
    done = set(
        db.execute(
            select(PriceReaction.event_id, PriceReaction.instrument).where(
                PriceReaction.event_id.in_([e.id for e in events])
            )
        ).all()
    )
    symbols = {s.code: s for s in db.scalars(select(PriceSymbol))}
    imap = market_prefs.instrument_map(db)
    out = []
    for e in events:
        for code in imap.get(e.currency.upper(), []):
            sym = symbols.get(code)
            if sym is None or sym.available is False or (e.id, code) in done:
                continue
            out.append((e, sym))
    return out


def _store(
    db: Session, event: Event, sym: PriceSymbol, results: dict[int, Horizon], user_id: int, now: datetime
) -> bool:
    for h, r in results.items():
        db.add(
            PriceReaction(
                event_id=event.id,
                instrument=sym.code,
                horizon_minutes=h,
                status=r.status,
                open_price=r.open,
                close_price=r.close,
                high=r.high,
                low=r.low,
                range_units=r.range_units,
                move_units=r.move_units,
                direction=r.direction,
                unit=sym.unit,
                computed_at=now,
                computed_with_user_id=user_id,
            )
        )
    try:
        db.commit()
        return True
    except IntegrityError:  # computed by someone else meanwhile: once is enough
        db.rollback()
        return False


def _cursor(db: Session) -> int:
    row = db.get(AppState, CURSOR_KEY)
    return int((row.value or {}).get("last_user_id", 0)) if row else 0


def _save_cursor(db: Session, user_id: int) -> None:
    row = db.get(AppState, CURSOR_KEY)
    if row is None:
        db.add(AppState(key=CURSOR_KEY, value={"last_user_id": user_id}))
    else:
        row.value = {"last_user_id": user_id}
    db.commit()


def run(db: Session, now: datetime | None = None) -> dict:
    now = now or utcnow()
    users = _opted_in(db)
    if not users:
        return {"skipped": "no opted-in users"}
    todo = _pending(db, now)
    if not todo:
        return {"computed": 0, "fetched": 0}

    # Rotate: start after whoever paid last.
    last = _cursor(db)
    users = [u for u in users if u[0].id > last] + [u for u in users if u[0].id <= last]
    accounts = {}
    turn = 0
    computed = fetched = 0
    charged: dict[int, int] = {}

    def next_payer() -> tuple[User, service.Account] | None:
        nonlocal turn
        for i in range(len(users)):
            user, prefs = users[(turn + i) % len(users)]
            if user.id not in accounts:
                accounts[user.id] = service.account_for(db, user, now)
            acct = accounts[user.id]
            if acct is None or acct.provider is None or allowance(db, user.id, prefs, now) < 1:
                continue
            turn = (turn + i + 1) % len(users)
            return user, acct
        return None

    for event, sym in todo:
        if fetched >= MAX_SERIES_PER_TICK:
            break
        payer = next_payer()
        if payer is None:
            break
        user, acct = payer
        release = event.at
        key = service.cache_key(acct, f"{sym.provider_symbol}|{SERIES_INTERVAL}|{release:%Y-%m-%dT%H:%M}")
        cached = service.cache_get(db, "series", key)
        if cached is not None:
            bars = [Bar(datetime.fromisoformat(t), o, h, lo, c) for t, o, h, lo, c in cached.payload or []]
            results = compute(bars, release, sym.pip_size)
        else:
            provider = acct.provider
            try:
                res = service.spend(
                    db,
                    acct,
                    1,
                    lambda p=provider, s=sym.provider_symbol, r=release: p.time_series(
                        s,
                        SERIES_INTERVAL,
                        start=r,
                        end=r + timedelta(minutes=61),
                        outputsize=SERIES_OUTPUTSIZE,
                    ),
                    now,
                    background=True,
                    block=False,
                )
            except ProviderError as exc:
                if exc.kind == "minute_limit":
                    break
                if exc.kind == "plan":
                    if not acct.fake:
                        resolved = service.resolve(db, sym.code)
                        service.record_availability(db, resolved, False, now)
                    _store(db, event, sym, {h: Horizon("unavailable") for h in HORIZONS}, user.id, now)
                    computed += 1
                    continue
                # invalid key, daily limit, network: this user sits out the rest of the tick
                accounts[user.id] = None  # type: ignore[assignment]
                continue
            fetched += 1
            charged[user.id] = charged.get(user.id, 0) + res.credits
            service.cache_put(
                db,
                "series",
                key,
                now=now,
                user_id=user.id,
                payload=[[b.t.isoformat(), b.open, b.high, b.low, b.close] for b in res.data],
            )
            results = compute(res.data, release, sym.pip_size)
            _save_cursor(db, user.id)
        if _store(db, event, sym, results, user.id, now):
            computed += 1
    return {"computed": computed, "fetched": fetched, "charged": charged, "pending": len(todo) - computed}
