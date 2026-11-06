"""Bulk screenshot matcher (U3): filename patterns, capture times, sequence fallback."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services import matcher as m

LONDON = ZoneInfo("Europe/London")


def trades(n=4, start=datetime(2026, 3, 2, 9, 0, tzinfo=UTC)):
    out = []
    for i in range(n):
        opened = start + timedelta(hours=3 * i)
        out.append(
            m.TradeRef(id=100 + i, index=i + 1, opened_at=opened, closed_at=opened + timedelta(minutes=50))
        )
    return out


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("T03_entry.png", (3, "entry")),
        ("t3-exit.png", (3, "outcome")),
        ("3e.png", (3, "entry")),
        ("3x.png", (3, "outcome")),
        ("T03_htf.png", (3, "htf")),
        ("3h.png", (3, "htf")),
        ("3o.png", (3, "outcome")),
        ("trade 3 entry.png", (3, "entry")),
        ("Trade3_exit.jpeg", (3, "outcome")),
        ("entry_t3.png", (3, "entry")),
        ("exit-03.webp", (3, "outcome")),
        ("T12 (entry).png", (12, "entry")),
        ("Screenshot 2026-11-05 at 23.25.13.png", None),
        ("05c71c5e906264d6.png", None),
        ("chart.png", None),
    ],
)
def test_parse_name(name, expected):
    assert m.parse_name(name) == expected


def test_filename_matches_are_high_confidence_and_fill_all_three_slots():
    files = [m.FileRef(f"T0{i}_{slot}.png") for i in range(1, 5) for slot in ("htf", "entry", "outcome")]
    result = m.match_files(trades(), files)
    assert len(result.matched) == 12 and not result.unmatched
    assert all(x.confidence == "high" for x in result.matches)
    by_file = {x.file: (x.trade_id, x.slot) for x in result.matches}
    assert by_file["T03_outcome.png"] == (102, "outcome") and by_file["T03_htf.png"] == (102, "htf")


def test_filename_for_a_filled_slot_goes_to_the_tray():
    ts = trades(2)
    ts[0].filled = ("entry",)
    result = m.match_files(ts, [m.FileRef("T01_entry.png"), m.FileRef("T01_exit.png")])
    assert result.unmatched[0].file == "T01_entry.png"
    assert result.matched[0].slot == "outcome"


def test_mac_screenshot_names_match_by_capture_time_in_the_strategy_timezone():
    ts = trades(2, start=datetime(2026, 7, 6, 8, 0, tzinfo=UTC))  # 09:00 BST open, 09:50 close
    files = [
        m.FileRef("Screenshot 2026-07-06 at 09.02.10.png"),
        m.FileRef("Screenshot 2026-07-06 at 08.58.00.png"),  # a second shot near the open: the HTF context
        m.FileRef("Screenshot 2026-07-06 at 09.55.00.png"),
        m.FileRef("Screenshot 2026-07-06 at 12.01.00.png"),  # second trade opens 12:00 BST
    ]
    result = m.match_files(ts, files, timezone="Europe/London")
    got = [(x.trade_id, x.slot, x.confidence) for x in result.matches]
    assert got == [
        (100, "entry", "medium"),
        (100, "htf", "medium"),
        (100, "outcome", "medium"),
        (101, "entry", "medium"),
    ]


def test_exif_time_close_to_the_open_is_high_confidence():
    ts = trades(1)
    f = m.FileRef("IMG_0001.jpg", captured_at=ts[0].opened_at + timedelta(minutes=5), time_source="exif")
    result = m.match_files(ts, [f])
    assert result.matches[0].confidence == "high" and result.matches[0].slot == "entry"


def test_times_too_far_from_any_trade_fall_back_to_sequence_as_low_confidence():
    ts = trades(2)
    far = datetime(2026, 11, 5, 23, 25, 13, tzinfo=UTC)
    files = [
        m.FileRef(f"{h}.png", captured_at=far + timedelta(seconds=i * 3)) for i, h in enumerate("abcdef")
    ]
    result = m.match_files(ts, files)
    assert [(x.trade_id, x.slot) for x in result.matches] == [
        (100, "htf"),
        (100, "entry"),
        (100, "outcome"),
        (101, "htf"),
        (101, "entry"),
        (101, "outcome"),
    ]
    assert all(x.confidence == "low" for x in result.matches)


def test_extra_files_with_no_free_slot_are_unmatched():
    result = m.match_files(trades(1), [m.FileRef(f"{i}.png") for i in range(4)])
    assert len(result.matched) == 3 and len(result.unmatched) == 1
    assert result.unmatched[0].reason == "no free slot"


def test_mixed_names_and_times():
    ts = trades(3)
    files = [
        m.FileRef("T02_entry.png"),
        m.FileRef("random.png", captured_at=ts[2].closed_at + timedelta(minutes=2), time_source="mtime"),
        m.FileRef("another.png"),
    ]
    result = m.match_files(ts, files)
    got = {x.file: (x.trade_id, x.slot, x.confidence) for x in result.matches}
    assert got["T02_entry.png"] == (101, "entry", "high")
    assert got["random.png"] == (102, "outcome", "medium")
    assert got["another.png"] == (100, "htf", "low")


def test_time_from_name_handles_fx_replay_style_stamps():
    assert m.time_from_name("chart 2026-07-06_09-02-10.png", LONDON) == datetime(
        2026, 7, 6, 9, 2, 10, tzinfo=LONDON
    )
    assert m.time_from_name("nothing.png", LONDON) is None
