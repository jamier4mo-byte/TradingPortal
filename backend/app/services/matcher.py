"""Bulk screenshot matcher (U3): pair dropped files with trades × (HTF, Entry, Outcome).

Three passes, in order of trust:
  1. filename: T03_htf.png, T03_entry.png, t3-outcome, 3h / 3e / 3o, "trade 3 entry", trade3_exit
  2. capture time: EXIF, the macOS "Screenshot 2026-11-05 at 23.25.13" name, or last-modified;
     matched to the nearest trade open/close in the strategy's timezone, within a tolerance
  3. sequence: whatever is left is laid into the empty slots in trade order (low confidence)
Pure Python so it can be unit-tested with synthetic names and times.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TIME_TOLERANCE = timedelta(minutes=90)
TIGHT_TOLERANCE = timedelta(minutes=20)

HTF_WORDS = ("htf", "h", "higher", "context", "bias", "daily", "4h", "1h")
ENTRY_WORDS = ("entry", "ent", "in", "open", "e", "before", "setup", "ltf")
OUTCOME_WORDS = ("outcome", "o", "exit", "ex", "out", "close", "x", "after", "result", "tp", "sl")
SLOT_WORDS = HTF_WORDS + ENTRY_WORDS + OUTCOME_WORDS
LABELLED = ("htf", "entry", "outcome")

MAC_SHOT = re.compile(r"screen\s*shot\s+(\d{4})-(\d{2})-(\d{2})\s+at\s+(\d{1,2})\.(\d{2})\.(\d{2})", re.I)
FX_SHOT = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ _T](\d{2})[.\-:](\d{2})(?:[.\-:](\d{2}))?")
# "T03_entry", "t3-exit", "trade 3 htf", "3e", "03x", "trade3_outcome", "T3 (entry)"
NAME_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(?:t(?:rade)?\s*[_\-#]?\s*)?(\d{1,3})\s*[_\-\s.()]*\s*("
    + "|".join(SLOT_WORDS)
    + r")(?![a-z])",
    re.I,
)
NAME_PATTERN_REVERSED = re.compile(
    r"(?:^|[^a-z0-9])("
    + "|".join(SLOT_WORDS)
    + r")\s*[_\-\s.()]*\s*(?:t(?:rade)?\s*[_\-#]?\s*)?(\d{1,3})(?![0-9])",
    re.I,
)


@dataclass
class TradeRef:
    id: int
    index: int  # 1-based position in the session
    opened_at: datetime  # aware
    closed_at: datetime | None
    filled: tuple[str, ...] = ()  # labelled slots that already hold a screenshot


@dataclass
class FileRef:
    name: str
    captured_at: datetime | None = None  # aware, from EXIF or the file's last-modified time
    time_source: str = "mtime"  # exif | name | mtime | none


@dataclass
class Match:
    file: str
    trade_id: int | None
    slot: str | None  # htf | entry | outcome
    confidence: str  # high | medium | low | none
    reason: str


@dataclass
class MatchResult:
    matches: list[Match] = field(default_factory=list)

    @property
    def matched(self) -> list[Match]:
        return [m for m in self.matches if m.trade_id is not None]

    @property
    def unmatched(self) -> list[Match]:
        return [m for m in self.matches if m.trade_id is None]


def slot_from_word(word: str) -> str:
    w = word.lower()
    if w in HTF_WORDS:
        return "htf"
    return "entry" if w in ENTRY_WORDS else "outcome"


def parse_name(name: str) -> tuple[int, str] | None:
    """('T03_entry.png') → (3, 'entry'); None when the name carries no trade hint."""
    stem = re.sub(r"\.[a-z0-9]{2,5}$", "", name.strip(), flags=re.I)
    if MAC_SHOT.search(stem) or FX_SHOT.search(stem):
        return None  # a timestamp, not a trade number
    m = NAME_PATTERN.search(stem) or NAME_PATTERN_REVERSED.search(stem)
    if not m:
        return None
    a, b = m.group(1), m.group(2)
    number, word = (a, b) if a.isdigit() else (b, a)
    return int(number), slot_from_word(word)


def time_from_name(name: str, zone: ZoneInfo) -> datetime | None:
    m = MAC_SHOT.search(name) or FX_SHOT.search(name)
    if not m:
        return None
    parts = [int(g) for g in m.groups() if g is not None]
    while len(parts) < 6:
        parts.append(0)
    y, mo, d, h, mi, s = parts
    try:
        return datetime(y, mo, d, h, mi, s, tzinfo=zone)
    except ValueError:
        return None


def match_files(
    trades: list[TradeRef], files: list[FileRef], *, timezone: str = "Europe/London"
) -> MatchResult:
    zone = ZoneInfo(timezone)
    by_index = {t.index: t for t in trades}
    taken: set[tuple[int, str]] = {(t.id, slot) for t in trades for slot in t.filled}
    result = MatchResult()
    pending: list[tuple[FileRef, datetime | None, str]] = []

    # Pass 1: filenames
    for f in files:
        hint = parse_name(f.name)
        if hint:
            idx, slot = hint
            trade = by_index.get(idx)
            if trade and (trade.id, slot) not in taken:
                taken.add((trade.id, slot))
                result.matches.append(
                    Match(f.name, trade.id, slot, "high", f"filename says trade {idx} {slot}")
                )
                continue
            if trade:
                result.matches.append(
                    Match(f.name, None, None, "none", f"trade {idx} {slot} already has a screenshot")
                )
                continue
        when = time_from_name(f.name, zone)
        source = "name" if when else f.time_source
        if when is None:
            when = f.captured_at
        pending.append((f, when, source))

    # Pass 2: capture time against open/close times. HTF context is captured around the entry too,
    # so the entry slot is tried first and HTF takes the second file near the open.
    still: list[tuple[FileRef, datetime | None, str]] = []
    for f, when, source in pending:
        if when is None:
            still.append((f, when, source))
            continue
        best: tuple[timedelta, TradeRef, str] | None = None
        for t in trades:
            for slot, moment in (("entry", t.opened_at), ("htf", t.opened_at), ("outcome", t.closed_at)):
                if moment is None or (t.id, slot) in taken:
                    continue
                delta = abs(when - moment)
                if delta <= TIME_TOLERANCE and (best is None or delta < best[0]):
                    best = (delta, t, slot)
        if best:
            delta, t, slot = best
            taken.add((t.id, slot))
            conf = "high" if source == "exif" and delta <= TIGHT_TOLERANCE else "medium"
            result.matches.append(
                Match(
                    f.name,
                    t.id,
                    slot,
                    conf,
                    f"{source} time is {int(delta.total_seconds() // 60)} min from the {slot}",
                )
            )
        else:
            still.append((f, when, source))

    # Pass 3: sequence. Files sorted by time (then name) fill empty slots in trade order: HTF, Entry, Outcome.
    still.sort(key=lambda item: (item[1] is None, item[1] or datetime.max.replace(tzinfo=zone), item[0].name))
    empty = [
        (t.id, slot)
        for t in sorted(trades, key=lambda t: t.index)
        for slot in LABELLED
        if (t.id, slot) not in taken
    ]
    for f, _when, _source in still:
        if empty:
            tid, slot = empty.pop(0)
            taken.add((tid, slot))
            result.matches.append(Match(f.name, tid, slot, "low", "placed by order; check it"))
        else:
            result.matches.append(Match(f.name, None, None, "none", "no free slot"))
    order = {f.name: i for i, f in enumerate(files)}
    result.matches.sort(key=lambda m: order.get(m.file, 0))
    return result
