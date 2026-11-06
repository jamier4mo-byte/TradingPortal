"""Synthetic news for `seed-dev` and the smoke suite: a believable week around `now`, plus a year of US CPI
and NFP releases with stored price reactions, and coverage so the seeded trades get tagged.

Dev data only (/tmp/tp-dev). Rows carry the source "synthetic" so they're never mistaken for feed data.
"""

import random
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ...models import Event, PriceReaction
from ..journal_rules import UK_TZ, to_uk
from . import catalogue, store
from .parse import MULTIPLIERS, format_figure, parse_figure, parse_value

SOURCE = "synthetic"
NEW_YORK = ZoneInfo("America/New_York")

# (weekday 0 = Monday, UK time or None for all day, currency, title, impact, forecast, previous)
WEEK: list[tuple[int, str | None, str, str, str, str, str]] = [
    (0, "00:30", "AUD", "Building Approvals m/m", "low", "2.1%", "-3.4%"),
    (0, "09:30", "EUR", "Sentix Investor Confidence", "low", "-12.4", "-13.2"),
    (0, "09:30", "GBP", "Flash Manufacturing PMI", "high", "49.8", "49.6"),
    (0, "14:45", "USD", "Flash Manufacturing PMI", "medium", "52.0", "52.2"),
    (0, "15:00", "USD", "ISM Manufacturing PMI", "high", "49.5", "48.7"),
    (0, "15:00", "USD", "Construction Spending m/m", "low", "0.2%", "-0.1%"),
    (1, "03:30", "AUD", "Cash Rate", "high", "3.60%", "3.60%"),
    (1, "07:00", "GBP", "Claimant Count Change", "high", "22.4K", "17.4K"),
    (1, "07:00", "GBP", "Unemployment Rate", "high", "4.8%", "4.8%"),
    (1, "10:00", "EUR", "German ZEW Economic Sentiment", "high", "39.5", "39.3"),
    (1, "13:30", "CAD", "Trade Balance", "low", "-5.4B", "-6.3B"),
    (1, "15:00", "USD", "JOLTS Job Openings", "high", "7.18M", "7.23M"),
    (1, "15:00", "USD", "CB Consumer Confidence", "high", "93.4", "94.2"),
    (2, None, "JPY", "Bank Holiday", "holiday", "", ""),
    (2, "00:30", "AUD", "CPI y/y", "medium", "2.4%", "2.1%"),
    (2, "07:00", "GBP", "CPI y/y", "high", "3.6%", "3.8%"),
    (2, "13:00", "EUR", "German Prelim CPI m/m", "high", "0.2%", "0.3%"),
    (2, "13:15", "USD", "ADP Non-Farm Employment Change", "high", "28K", "-32K"),
    (2, "14:45", "CAD", "Overnight Rate", "high", "2.25%", "2.50%"),
    (2, "15:30", "USD", "Crude Oil Inventories", "low", "-1.2M", "2.4M"),
    (2, "19:00", "USD", "FOMC Meeting Minutes", "high", "", ""),
    (3, "00:30", "AUD", "Employment Change", "high", "20.1K", "14.9K"),
    (3, "00:30", "AUD", "Unemployment Rate", "high", "4.3%", "4.3%"),
    (3, "07:00", "GBP", "GDP m/m", "high", "0.1%", "-0.1%"),
    (3, "07:30", "CHF", "CPI m/m", "medium", "0.1%", "-0.2%"),
    (3, "12:00", "GBP", "Official Bank Rate", "high", "4.00%", "4.00%"),
    (3, "13:15", "EUR", "Main Refinancing Rate", "high", "2.15%", "2.15%"),
    (3, "13:30", "USD", "Unemployment Claims", "high", "226K", "218K"),
    (3, "13:30", "USD", "PPI m/m", "medium", "0.2%", "-0.1%"),
    (3, "13:45", "EUR", "ECB Press Conference", "high", "", ""),
    (3, "21:45", "NZD", "Visitor Arrivals m/m", "low", "", "1.2%"),
    (4, "00:30", "JPY", "Tokyo Core CPI y/y", "medium", "2.6%", "2.5%"),
    (4, "07:00", "GBP", "Retail Sales m/m", "high", "0.3%", "0.5%"),
    (4, "08:15", "EUR", "French Flash Services PMI", "low", "48.6", "48.0"),
    (4, "13:30", "USD", "Non-Farm Employment Change", "high", "110K", "22K"),
    (4, "13:30", "USD", "Unemployment Rate", "high", "4.3%", "4.3%"),
    (4, "13:30", "USD", "Average Hourly Earnings m/m", "high", "0.3%", "0.3%"),
    (4, "13:30", "CAD", "Employment Change", "high", "5.0K", "-65.5K"),
    (4, "15:00", "USD", "Prelim UoM Consumer Sentiment", "high", "53.2", "55.1"),
]
SOON = ("USD", "Core PCE Price Index m/m", "high", "0.2%", "0.2%")  # within ~2 hours of the seed
LATER = ("USD", "Fed Chair Powell Speaks", "high", "", "")  # later today

# Price reactions: (instrument, unit, 15-minute range low/high). 5 and 60 minutes scale from 15.
REACTIONS = (("XAUUSD", "points", 110.0, 260.0), ("EURUSD", "pips", 14.0, 42.0))
SCALE = {5: 0.55, 15: 1.0, 60: 1.65}


def _uk(d: date, hhmm: str | None) -> datetime:
    t = time(0) if hhmm is None else time(*(int(x) for x in hhmm.split(":")))
    return datetime.combine(d, t, tzinfo=UK_TZ).astimezone(UTC)


def _actual(rng: random.Random, forecast: str) -> str | None:
    fig = parse_figure(forecast)
    if fig is None:
        return None
    step = 10 ** (-fig.decimals) if fig.decimals else (5 if fig.unit == "K" else 1)
    mult = MULTIPLIERS[fig.unit]
    moved = fig.value / mult + rng.choice((-3, -2, -1, 0, 1, 2, 3)) * step
    return format_figure(moved * mult, fig.unit, fig.decimals)


def _event(
    db: Session,
    idx: catalogue.TypeIndex,
    *,
    currency: str,
    title: str,
    impact: str,
    at: datetime,
    forecast: str,
    previous: str,
    actual: str | None,
    all_day: bool = False,
) -> Event:
    et = catalogue.resolve(db, idx, currency, title)
    ev = Event(
        title=title,
        currency=currency,
        at=at,
        all_day=all_day,
        impact=impact,
        event_type_id=et.id,
        forecast=forecast or None,
        previous=previous or None,
        actual=actual,
        forecast_value=parse_value(forecast),
        previous_value=parse_value(previous),
        actual_value=parse_value(actual),
        actual_at=at + timedelta(minutes=1) if actual else None,
        sources=[SOURCE],
        last_fetched_at=at,
    )
    db.add(ev)
    return ev


def _monday(now: datetime) -> date:
    uk = to_uk(now).date()
    if uk.weekday() >= 5:
        return uk + timedelta(days=7 - uk.weekday())
    return uk - timedelta(days=uk.weekday())


def _first_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    return d + timedelta(days=(4 - d.weekday()) % 7)


def _weekday_on_or_after(d: date) -> date:
    return d + timedelta(days=(7 - d.weekday()) % 7) if d.weekday() >= 5 else d


def _reactions(rng: random.Random, ev: Event) -> list[PriceReaction]:
    out = []
    for inst, unit, lo, hi in REACTIONS:
        base = rng.uniform(lo, hi)
        sign = rng.choice((1, -1))
        for h, k in SCALE.items():
            rng_units = round(base * k * rng.uniform(0.85, 1.15), 1)
            move = round(sign * rng_units * rng.uniform(0.2, 0.75), 1)
            out.append(
                PriceReaction(
                    event_id=ev.id,
                    instrument=inst,
                    horizon_minutes=h,
                    status="ok",
                    range_units=rng_units,
                    move_units=move,
                    direction="up" if move > 0 else "down" if move < 0 else "flat",
                    unit=unit,
                    computed_at=ev.at + timedelta(minutes=h + 5),
                )
            )
    return out


def seed(db: Session, now: datetime, *, seed: int = 4) -> dict:
    """Insert the synthetic week, a year of US CPI and NFP with reactions, and coverage. Commits."""
    rng = random.Random(seed)
    idx = catalogue.TypeIndex.load(db)
    monday = _monday(now)
    week: list[Event] = []
    for day, hhmm, cur, title, impact, forecast, previous in WEEK:
        at = _uk(monday + timedelta(days=day), hhmm)
        actual = _actual(rng, forecast) if at < now and forecast else None
        week.append(
            _event(
                db,
                idx,
                currency=cur,
                title=title,
                impact=impact,
                at=at,
                forecast=forecast,
                previous=previous,
                actual=actual,
                all_day=hhmm is None,
            )
        )
    soon = (now + timedelta(minutes=75)).replace(second=0, microsecond=0)
    soon -= timedelta(minutes=soon.minute % 5)
    end_of_today = _uk(to_uk(now).date() + timedelta(days=1), None) - timedelta(minutes=15)
    later = min(now + timedelta(hours=4), end_of_today).replace(second=0, microsecond=0)
    later -= timedelta(minutes=later.minute % 15)
    if later <= soon:
        later = soon + timedelta(minutes=15)
    for (cur, title, impact, forecast, previous), at in ((SOON, soon), (LATER, later)):
        week.append(
            _event(
                db, idx, currency=cur, title=title, impact=impact, at=at,
                forecast=forecast, previous=previous, actual=None,
            )
        )  # fmt: skip

    history: list[Event] = []
    today = to_uk(now).date()
    for back in range(1, 13):
        y, m = today.year, today.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        cpi_day = _weekday_on_or_after(date(y, m, 13))
        nfp_day = _first_friday(y, m)
        for title, d, forecast, spread in (
            ("CPI m/m", cpi_day, rng.choice(("0.2%", "0.3%", "0.4%")), 0.1),
            ("Non-Farm Employment Change", nfp_day, f"{rng.randrange(60, 240, 5)}K", 40.0),
        ):
            at = datetime.combine(d, time(8, 30), tzinfo=NEW_YORK).astimezone(UTC)
            if at >= now - timedelta(days=1):
                continue
            fig = parse_figure(forecast)
            assert fig is not None
            mult = MULTIPLIERS[fig.unit]

            def figure(scaled: float, fig=fig, mult=mult) -> str:
                return format_figure(scaled * mult, fig.unit, fig.decimals)

            scaled = fig.value / mult
            actual = figure(scaled + rng.choice((-2, -1, 0, 1, 2)) * spread / 2)
            prev = figure(scaled + rng.choice((-1, 0, 1)) * spread / 2)
            history.append(
                _event(
                    db, idx, currency="USD", title=title, impact="high", at=at,
                    forecast=forecast, previous=prev, actual=actual,
                )
            )  # fmt: skip
    # Weekly jobless claims (Thursdays 08:30 New York) so seeded trades land inside some news windows.
    claims = 0
    thursday = today - timedelta(days=(today.weekday() - 3) % 7 or 7)
    while thursday >= today - timedelta(days=365):
        at = datetime.combine(thursday, time(8, 30), tzinfo=NEW_YORK).astimezone(UTC)
        forecast = f"{rng.randrange(205, 245)}K"
        actual = f"{int(forecast[:-1]) + rng.randrange(-12, 13)}K"
        _event(db, idx, currency="USD", title="Unemployment Claims", impact="high", at=at,
               forecast=forecast, previous=f"{rng.randrange(205, 245)}K", actual=actual)  # fmt: skip
        claims += 1
        thursday -= timedelta(days=7)
    # Monthly ISM surveys (10:00 New York): first and third business days.
    for back in range(1, 13):
        y, m = today.year, today.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        days = [date(y, m, d) for d in range(1, 8) if date(y, m, d).weekday() < 5]
        for title, d in (("ISM Manufacturing PMI", days[0]), ("ISM Services PMI", days[2])):
            at = datetime.combine(d, time(10), tzinfo=NEW_YORK).astimezone(UTC)
            forecast = f"{rng.uniform(47.5, 53.5):.1f}"
            actual = f"{float(forecast) + rng.choice((-1.2, -0.6, 0.0, 0.5, 1.1)):.1f}"
            _event(db, idx, currency="USD", title=title, impact="high", at=at,
                   forecast=forecast, previous=f"{rng.uniform(47.5, 53.5):.1f}", actual=actual)  # fmt: skip
    db.flush()
    reactions = [r for ev in history for r in _reactions(rng, ev)]
    db.add_all(reactions)
    start = today - timedelta(days=365)
    store.record_coverage(db, SOURCE, start, monday + timedelta(days=6), note="Synthetic dev data")
    db.commit()
    return {"week": len(week), "history": len(history), "claims": claims, "reactions": len(reactions)}
