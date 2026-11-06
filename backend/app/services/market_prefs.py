"""Per-user News Room and price preferences, and the event-currency ↔ instrument mapping.

Shared by the news tagging, the calendar's "my instruments only" filter, alerts and prices.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import NewsInstrumentMap, User, UserMarketPrefs

# FX majors, gold, bitcoin, GER40 and NAS100 (Prompt 4 default).
DEFAULT_INSTRUMENTS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "AUDUSD",
    "USDCAD",
    "NZDUSD",
    "XAUUSD",
    "BTCUSD",
    "GER40",
    "NAS100",
]
DEFAULT_WINDOW_MINUTES = 15
MIN_WINDOW_MINUTES, MAX_WINDOW_MINUTES = 0, 120
DEFAULT_BACKGROUND_CAP = 150


def get_prefs(db: Session, user: User | int) -> UserMarketPrefs:
    """The user's row, or an unsaved row holding the defaults."""
    user_id = user if isinstance(user, int) else user.id
    row = db.get(UserMarketPrefs, user_id)
    if row is None:
        row = UserMarketPrefs(
            user_id=user_id,
            instruments=list(DEFAULT_INSTRUMENTS),
            news_window_minutes=DEFAULT_WINDOW_MINUTES,
            allow_background_jobs=False,
            background_daily_cap=DEFAULT_BACKGROUND_CAP,
        )
    return row


def save_prefs(db: Session, user: User, **changes) -> UserMarketPrefs:
    row = db.get(UserMarketPrefs, user.id)
    if row is None:
        row = get_prefs(db, user)
        db.add(row)
    for key, value in changes.items():
        if value is not None:
            setattr(row, key, value)
    db.commit()
    return row


def instrument_map(db: Session) -> dict[str, list[str]]:
    """currency → instruments, e.g. {"USD": ["XAUUSD", "BTCUSD", "EURUSD", "NAS100"], ...}."""
    out: dict[str, list[str]] = {}
    for row in db.scalars(select(NewsInstrumentMap).order_by(NewsInstrumentMap.id)):
        out.setdefault(row.currency.upper(), []).append(row.instrument.upper())
    return out


def currencies_for(db: Session, instruments: list[str]) -> set[str]:
    """Event currencies that move any of these instruments (reverse of the map)."""
    wanted = {i.upper() for i in instruments}
    return {cur for cur, insts in instrument_map(db).items() if wanted & set(insts)}


def instruments_for(db: Session, currency: str) -> list[str]:
    return instrument_map(db).get(currency.upper(), [])
