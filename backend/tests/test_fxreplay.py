"""FX Replay CSV parser: real header, BOM, quoting, dates, DST, empty cells, tags, bad rows."""

from datetime import UTC, datetime

import pytest

from app.services import fxreplay as fx
from app.services.journal_rules import classify_outcome, market_date, session_label
from tests.conftest import FIXTURES

SAMPLE = (FIXTURES / "fxreplay-sample.csv").read_bytes()


def test_parses_the_real_header_with_a_bom_and_crlf():
    result = fx.parse_csv(SAMPLE)
    assert len(result.rows) == 10
    assert result.unknown_columns == []
    assert result.rows[0].fx_id == "100000001"
    assert result.rows[0].pair == "OANDA:NAS100USD"
    assert result.rows[0].raw["currentRealizedBalance"] == "10250.0"


def test_malformed_rows_are_reported_not_fatal():
    result = fx.parse_csv(SAMPLE)
    assert len(result.problems) == 2
    assert "line 12" in result.problems[0] and "buy or sell" in result.problems[0]
    assert "line 13" in result.problems[1] and "not a date" in result.problems[1]
    assert result.total_rows == 12


def test_clock_times_convert_from_europe_london_to_utc():
    result = fx.parse_csv(SAMPLE, timezone="Europe/London")
    jan = result.rows[0]  # GMT: no offset
    assert jan.opened_at == datetime(2026, 1, 12, 9, 30, tzinfo=UTC)
    may = result.rows[4]  # BST: one hour behind the clock
    assert may.opened_at == datetime(2026, 5, 20, 12, 45, tzinfo=UTC)


def test_dst_boundaries_spring_forward_and_fall_back():
    rows = {r.fx_id: r for r in fx.parse_csv(SAMPLE).rows}
    spring = rows["100000003"]  # 29 Mar 2026: 01:00 GMT becomes 02:00 BST
    assert spring.opened_at == datetime(2026, 3, 29, 0, 30, tzinfo=UTC)
    assert spring.closed_at == datetime(2026, 3, 29, 1, 30, tzinfo=UTC)
    assert (spring.closed_at - spring.opened_at).total_seconds() == 3600  # the clock said 2h, it was 1h
    autumn = rows["100000010"]  # 25 Oct 2026: 02:00 BST becomes 01:00 GMT
    assert autumn.opened_at == datetime(2026, 10, 24, 23, 30, tzinfo=UTC)
    assert autumn.closed_at == datetime(2026, 10, 25, 3, 0, tzinfo=UTC)


def test_utc_timezone_option_leaves_the_clock_alone():
    result = fx.parse_csv(SAMPLE, timezone="UTC")
    assert result.rows[4].opened_at == datetime(2026, 5, 20, 13, 45, tzinfo=UTC)


def test_market_date_and_session_follow_uk_time():
    rows = {r.fx_id: r for r in fx.parse_csv(SAMPLE).rows}
    near_midnight = rows["100000008"]  # 00:20 BST on 7 Jul = 23:20 UTC on 6 Jul
    assert near_midnight.opened_at.date().isoformat() == "2026-07-06"
    assert market_date(near_midnight.opened_at).isoformat() == "2026-07-07"
    assert session_label(near_midnight.opened_at) == "Asia"
    assert session_label(rows["100000001"].opened_at) == "London"
    assert session_label(rows["100000005"].opened_at) == "New York"


def test_breakeven_at_plus_minus_ten_dollars():
    assert classify_outcome(250.0) == "win"
    assert classify_outcome(-100.0) == "loss"
    assert classify_outcome(1.5) == "breakeven"
    assert classify_outcome(-10.0) == "breakeven"  # inclusive at both ends
    assert classify_outcome(10.0) == "breakeven"
    assert classify_outcome(10.01) == "win"
    assert classify_outcome(-10.01) == "loss"
    assert classify_outcome(5.0, threshold=2) == "win"  # a user's own setting still wins
    outcomes = [classify_outcome(r.pnl) for r in fx.parse_csv(SAMPLE).rows]
    assert outcomes.count("win") == 6 and outcomes.count("loss") == 2 and outcomes.count("breakeven") == 2


def test_tags_split_on_fx_replay_separators_and_quoted_cells():
    rows = {r.fx_id: r for r in fx.parse_csv(SAMPLE).rows}
    assert rows["100000003"].tags == ["FVG", "Order block"]
    assert rows["100000001"].tags == []
    assert fx.split_tags("a, b|c;d") == ["a", "b", "c", "d"]


def test_realised_r_matches_fx_replay_avg_rr():
    for row in fx.parse_csv(SAMPLE).rows:
        r = fx.realised_r(row.side, row.entry_price, row.initial_sl, row.exit_price)
        assert r == pytest.approx(row.avg_rr, abs=0.006)


def test_duplicate_ids_within_one_file_are_skipped_and_reported():
    text = SAMPLE.decode("utf-8-sig").splitlines()
    doubled = "\n".join([*text, text[1]])
    result = fx.parse_csv(doubled)
    assert len(result.rows) == 10
    assert result.duplicate_in_file == ["100000001"]
    assert any("appears twice" in p for p in result.problems)


def test_missing_columns_and_empty_files_are_format_errors():
    with pytest.raises(fx.CsvFormatError, match="Missing columns"):
        fx.parse_csv("id,dateStart\n1,2026/01/01 10:00:00\n")
    with pytest.raises(fx.CsvFormatError, match="empty"):
        fx.parse_csv("   \n")
    with pytest.raises(fx.CsvFormatError, match="timezone"):
        fx.parse_csv(SAMPLE, timezone="Mars/Olympus")


def test_other_date_formats_and_thousands_commas():
    header = fx.KNOWN_COLUMNS
    row = dict.fromkeys(header, "")
    row.update(
        id="7",
        dateStart="2026-02-01T10:00:00",
        dateEnd="01/02/2026 11:30",
        pair="GOLD",
        rPnL='"1,250.5"',
        side="BUY",
        entryPrice="2900",
        initialSL="2890",
    )
    text = ",".join(header) + "\n" + ",".join(row[c] for c in header) + "\n"
    parsed = fx.parse_csv(text).rows[0]
    assert parsed.pnl == 1250.5
    assert parsed.side == "buy"
    assert parsed.closed_at.hour == 11 and parsed.max_tp is None and parsed.status == "closed"
