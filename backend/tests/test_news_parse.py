"""News figures, surprises, title matching and both feeds' times → UTC across DST."""

import json
from datetime import UTC, datetime

import pytest

from app.services.journal_rules import to_uk
from app.services.news import catalogue, ff, jblanked
from app.services.news.parse import format_figure, parse_figure, parse_value, style_like, surprise
from tests.conftest import FIXTURES

NEWS = FIXTURES / "news"


def ff_items(name: str) -> list[dict]:
    return ff.parse_items(json.loads((NEWS / name).read_text()))


@pytest.mark.parametrize(
    ("text", "value", "unit", "decimals"),
    [
        ("0.3%", 0.3, "%", 1),
        ("185K", 185000.0, "K", 0),
        ("-1.2B", -1.2e9, "B", 1),
        ("−65.5K", -65500.0, "K", 1),
        ("<0.1", 0.1, "", 1),
        ("7.18M", 7.18e6, "M", 2),
        ("4.00%", 4.0, "%", 2),
        ("49.5", 49.5, "", 1),
        (" 226K ", 226000.0, "K", 0),
    ],
)
def test_parse_figure(text, value, unit, decimals):
    fig = parse_figure(text)
    assert fig is not None
    assert fig.value == pytest.approx(value)
    assert (fig.unit, fig.decimals) == (unit, decimals)


@pytest.mark.parametrize("text", [None, "", "   ", "n/a", "Tentative"])
def test_blank_or_unreadable_figures_are_none(text):
    assert parse_figure(text) is None and parse_value(text) is None


def test_format_and_style_like_follow_forex_factory():
    assert format_figure(-65500, "K", 1) == "-65.5K"
    assert format_figure(0.3, "%", 1) == "0.3%"
    assert style_like(254.0, "110K", "22K") == ("254K", 254000.0)
    assert style_like(4.2, "4.3%") == ("4.2%", 4.2)
    assert style_like(0.25, "0.3%") == ("0.25%", 0.25)  # keep the precision the number needs
    assert style_like(51.9, None, "55.1") == ("51.9", 51.9)
    assert style_like(13.1) == ("13.1", 13.1)  # no Forex Factory style to copy
    assert style_like(None, "1%") == (None, None)


def test_surprise_wording_direction_and_units():
    nfp = surprise("254K", "110K", 254000, 110000, True)
    assert nfp == {
        "direction": "up",
        "diff": 144.0,
        "diff_text": "+144K",
        "better": True,
        "wording": "Better than forecast",
    }
    jobless = surprise("4.2%", "4.3%", 4.2, 4.3, False)
    assert jobless["direction"] == "down" and jobless["diff_text"] == "−0.1%"
    assert jobless["better"] is True and jobless["wording"] == "Better than forecast"
    cpi = surprise("0.2%", "0.3%", 0.2, 0.3, True)
    assert cpi["better"] is False and cpi["wording"] == "Worse than forecast"
    speech = surprise("15K", "30K", 15000, 30000, None)
    assert speech["better"] is None and speech["wording"] == "Below forecast"
    assert speech["diff_text"] == "−15K"
    inline = surprise("0.30%", "0.3%", 0.3, 0.3000000001, True)
    assert inline["direction"] == "inline" and inline["wording"] == "In line with forecast"
    assert surprise(None, "0.3%", None, 0.3, True) is None
    assert surprise("0.3%", None, 0.3, None, True) is None


def test_title_matching_uses_aliases_wildcards_and_currency(db):
    idx = catalogue.TypeIndex.load(db)
    nfp = idx.match("USD", "Non-Farm Employment Change")
    assert nfp is not None and nfp.key == "USD:nfp"
    assert idx.match("USD", "Nonfarm Payrolls") is nfp
    assert idx.match("usd", "non farm employment change") is nfp
    assert idx.match("USD", "Fed Chair Powell Speaks").key == "USD:fed_chair_speaks"
    assert idx.match("EUR", "ECB President Lagarde Speaks").key == "EUR:ecb_president_speaks"
    assert idx.match("USD", "Fed Interest Rate Decision").key == "USD:fed_rate"
    assert idx.match("GBP", "Unemployment Rate").key == "GBP:unemployment_rate"
    assert idx.match("USD", "Unemployment Rate").key == "USD:unemployment_rate"
    assert idx.match("USD", "FOMC Member Waller Speaks") is None  # not the Chair: unseeded type
    assert idx.match("EUR", "Non-Farm Employment Change") is None


def test_seeded_types_have_explanations(db):
    from sqlalchemy import select

    from app.models import EventType

    seeded = list(db.scalars(select(EventType).where(EventType.seeded.is_(True))))
    assert len(seeded) >= 34
    assert all(t.explanation and t.why_it_matters and t.aliases for t in seeded)
    by_key = {t.key: t for t in seeded}
    assert by_key["USD:unemployment_rate"].higher_is_better is False
    assert by_key["USD:claims"].higher_is_better is False
    assert by_key["USD:cpi_mm"].higher_is_better is True
    assert by_key["USD:fed_chair_speaks"].higher_is_better is None


# ---- times --------------------------------------------------------------------------------------


def _at(items: list[dict], currency: str, title: str) -> datetime:
    return next(i["at"] for i in items if i["currency"] == currency and i["title"] == title)


def test_forex_factory_times_to_utc_across_the_us_dst_change():
    items = ff_items("ff_week_2026-11-01.json")
    # Sunday 1 Nov, 01:30 New York is still EDT (-04:00); the clocks go back at 02:00.
    assert _at(items, "AUD", "MI Inflation Gauge m/m") == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    # After the change: 08:30 EST = 13:30 UTC = 13:30 UK (both on winter time).
    nfp = _at(items, "USD", "Non-Farm Employment Change")
    assert nfp == datetime(2026, 11, 6, 13, 30, tzinfo=UTC)
    assert to_uk(nfp).strftime("%Y-%m-%d %H:%M") == "2026-11-06 13:30"
    # A Sunday-evening New York time is Monday in the UK.
    caixin = _at(items, "CNY", "Caixin Manufacturing PMI")
    assert to_uk(caixin).strftime("%a %H:%M") == "Mon 02:45"
    assert ff.week_of(items) == (datetime(2026, 11, 1).date(), datetime(2026, 11, 7).date())
    holiday = next(i for i in items if i["impact"] == "holiday")
    assert holiday["all_day"] is True


def test_forex_factory_gap_week_uk_on_gmt_us_still_on_edt():
    items = ff_items("ff_week_2026-10-25.json")
    gdp = _at(items, "USD", "Advance GDP q/q")
    assert gdp == datetime(2026, 10, 29, 12, 30, tzinfo=UTC)
    assert to_uk(gdp).strftime("%H:%M") == "12:30"  # an hour earlier than usual for UK traders
    fomc = _at(items, "USD", "Federal Funds Rate")
    assert to_uk(fomc).strftime("%H:%M") == "18:00"
    ecb = _at(items, "EUR", "Main Refinancing Rate")
    assert to_uk(ecb).strftime("%H:%M") == "13:15"


def test_jblanked_server_time_is_gmt_plus_2_in_winter_and_plus_3_in_summer():
    assert jblanked.parse_date("2026.11.06 15:30:00") == datetime(2026, 11, 6, 13, 30, tzinfo=UTC)
    assert jblanked.parse_date("2026.07.15 15:30:00") == datetime(2026, 7, 15, 12, 30, tzinfo=UTC)
    assert jblanked.parse_date("2026-07-15 15:30:00") == datetime(2026, 7, 15, 12, 30, tzinfo=UTC)
    # Late-October gap week: EU already on winter time (+2), so 14:30 server = 12:30 UTC.
    assert jblanked.parse_date("2026.10.29 14:30:00") == datetime(2026, 10, 29, 12, 30, tzinfo=UTC)
    with pytest.raises(ValueError):
        jblanked.parse_date("06/11/2026 15:30")


def test_jblanked_items_parse_ids_and_impacts():
    items = jblanked.parse_items(json.loads((NEWS / "jb_today_2026-11-06.json").read_text()))
    nfp = items[0]
    assert nfp["event_id"] == 840030016 and nfp["actual"] == 254.0 and nfp["impact"] == "high"
    assert items[4]["event_id"] is None  # Event_ID null
    assert items[5]["event_id"] is None and items[5]["impact"] == "low"  # Event_ID missing
    with pytest.raises(ValueError):
        jblanked.parse_items({"detail": "nope"})
