"""Instrument lookup: FX Replay pairs like OANDA:NAS100USD → NAS100, with pip/point size."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Instrument


def pair_symbol(pair: str) -> str:
    """Strip the broker prefix and punctuation: 'OANDA:NAS100USD' → 'NAS100USD', 'EUR/USD' → 'EURUSD'."""
    name = pair.strip().rsplit(":", 1)[-1]
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def _key(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def find_instrument(db: Session, pair: str) -> Instrument | None:
    key = pair_symbol(pair)
    if not key:
        return None
    instruments = list(db.scalars(select(Instrument)))
    for inst in instruments:
        if _key(inst.symbol) == key or any(_key(a) == key for a in inst.aliases or []):
            return inst
    # Last resort: an alias or symbol the pair starts with (NAS100USD → NAS100, XAUUSDm → XAUUSD)
    for inst in instruments:
        for cand in [inst.symbol, *(inst.aliases or [])]:
            if key.startswith(_key(cand)):
                return inst
    return None


def canonical_symbol(db: Session, pair: str) -> str:
    inst = find_instrument(db, pair)
    return inst.symbol if inst else pair_symbol(pair)


def fallback_pip_size(symbol: str) -> tuple[float, str]:
    """When the instrument isn't in the table: FX pairs use pips, everything else points."""
    if re.fullmatch(r"[A-Z]{6}", symbol) and not symbol.startswith(("XAU", "XAG")):
        return (0.01, "pips") if "JPY" in symbol else (0.0001, "pips")
    return (1.0, "points")


def pip_size_for(db: Session, pair: str) -> tuple[float, str]:
    inst = find_instrument(db, pair)
    if inst:
        return inst.pip_size, inst.unit
    return fallback_pip_size(pair_symbol(pair))
