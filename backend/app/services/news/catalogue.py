"""Event-type matching: feed titles → event types (seeded by migration 0008, with aliases).

Matching is per currency and ignores case and punctuation ("CPI m/m" == "cpi mm"). An alias holding "*"
is a wildcard pattern, used for speeches ("Fed Chair * Speaks" matches "Fed Chair Powell Speaks").
A title that matches nothing creates an unseeded event type keyed "CUR:slug", without an explanation.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import EventType

COUNTRY = {
    "USD": "US",
    "EUR": "Euro area",
    "GBP": "UK",
    "JPY": "Japan",
    "AUD": "Australia",
    "CAD": "Canada",
    "CHF": "Switzerland",
    "NZD": "New Zealand",
    "CNY": "China",
}


def normalise(title: str) -> str:
    """Lower case, "/" and punctuation dropped, spaces collapsed: "Core CPI m/m" → "core cpi mm"."""
    s = title.lower().replace("&", " and ").replace("/", "")
    s = re.sub(r"[^a-z0-9%*]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:60] or "event"


def type_key(currency: str, title: str) -> str:
    return f"{currency.upper()}:{slug(title)}"


def display_name(name: str, currency: str) -> str:
    """ "US CPI m/m", "UK GDP m/m"; names that already say where ("German ZEW…") stay as they are."""
    if name.split(" ", 1)[0] in ("German", "ECB", "Fed", "FOMC", "BoE", "BoJ", "RBA", "BoC", "SNB", "RBNZ"):
        return name
    country = COUNTRY.get(currency.upper())
    return f"{country} {name}" if country else f"{currency} {name}"


@dataclass
class TypeIndex:
    """Every event type in memory for one fetch: exact aliases and wildcard patterns, per currency."""

    exact: dict[tuple[str, str], EventType] = field(default_factory=dict)
    patterns: list[tuple[str, re.Pattern, EventType]] = field(default_factory=list)
    by_key: dict[str, EventType] = field(default_factory=dict)

    @classmethod
    def load(cls, db: Session) -> "TypeIndex":
        idx = cls()
        # Seeded rows first, so a seeded alias wins over an unseeded row with the same title.
        for et in db.scalars(select(EventType).order_by(EventType.seeded.desc(), EventType.id)):
            idx.add(et)
        return idx

    def add(self, et: EventType) -> None:
        self.by_key[et.key] = et
        cur = et.currency.upper()
        for alias in [et.name, *(et.aliases or [])]:
            norm = normalise(alias)
            if "*" in norm:
                parts = [re.escape(p.strip()) for p in norm.split("*")]
                self.patterns.append((cur, re.compile("^" + r"\b.*\b".join(parts) + "$"), et))
            else:
                self.exact.setdefault((cur, norm), et)

    def match(self, currency: str, title: str) -> EventType | None:
        cur, norm = currency.upper(), normalise(title)
        hit = self.exact.get((cur, norm))
        if hit:
            return hit
        for pcur, pattern, et in self.patterns:
            if pcur == cur and pattern.match(norm):
                return et
        return None


def resolve(db: Session, idx: TypeIndex, currency: str, title: str) -> EventType:
    """The matching event type, or a new unseeded one for this currency and title."""
    hit = idx.match(currency, title)
    if hit:
        return hit
    key = type_key(currency, title)
    existing = idx.by_key.get(key)
    if existing:
        return existing
    et = EventType(
        key=key,
        name=title.strip()[:120],
        currency=currency.upper()[:8],
        category="",
        higher_is_better=None,
        aliases=[title.strip()],
        seeded=False,
    )
    db.add(et)
    db.flush()
    idx.add(et)
    return et
