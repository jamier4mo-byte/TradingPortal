"""International bank holidays for the News Room (amends, Nov 2026), computed offline with `holidays`.

Forex Factory only lists a holiday in the week it publishes, so dates further out come from the rules here:
one market centre per calendar currency (the one whose banks set that currency's liquidity). No network,
no storage: a pure function of the date range, cached per year.
"""

from datetime import date
from functools import lru_cache

import holidays

# currency → (label, country code, subdivision or None, financial calendar or None)
CENTRES: dict[str, tuple[str, str, str | None, str | None]] = {
    "USD": ("United States", "US", None, None),
    "EUR": ("Euro area (TARGET)", "", None, "ECB"),
    "GBP": ("United Kingdom", "GB", "ENG", None),
    "JPY": ("Japan", "JP", None, None),
    "AUD": ("Australia (Sydney)", "AU", "NSW", None),
    "CAD": ("Canada", "CA", None, None),
    "CHF": ("Switzerland (Zurich)", "CH", "ZH", None),
    "NZD": ("New Zealand", "NZ", None, None),
    "CNY": ("China", "CN", None, None),
}
MAX_DAYS = 400


@lru_cache(maxsize=64)
def _year(currency: str, year: int) -> tuple[tuple[date, str], ...]:
    _, country, subdiv, financial = CENTRES[currency]
    try:
        if financial:
            cal = holidays.financial_holidays(financial, years=year)
        else:
            cal = holidays.country_holidays(country, subdiv=subdiv, years=year, language="en_US")
    except (NotImplementedError, KeyError, ValueError):
        return ()
    return tuple(sorted(cal.items()))


def between(start: date, end: date, currencies: list[str] | None = None) -> list[dict]:
    """Holidays from `start` to `end` inclusive, weekdays only (a Saturday holiday closes nothing extra),
    sorted by date then currency. `currencies` narrows the list; unknown codes are ignored."""
    if end < start:
        start, end = end, start
    wanted = [c for c in (currencies or list(CENTRES)) if c in CENTRES]
    out: list[dict] = []
    for cur in wanted:
        label = CENTRES[cur][0]
        for year in range(start.year, end.year + 1):
            for day, name in _year(cur, year):
                if start <= day <= end and day.weekday() < 5:
                    for part in str(name).split("; "):
                        out.append({"date": day.isoformat(), "currency": cur, "centre": label, "name": part})
    out.sort(key=lambda h: (h["date"], list(CENTRES).index(h["currency"]), h["name"]))
    return out
