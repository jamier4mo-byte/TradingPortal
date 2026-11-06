"""FX Replay CSV parser (F3). Pure: no database, no timezone conversion beyond what it's told.

The Analytics export has these 22 columns (looked up by name, so order doesn't matter):
  id, dateStart, dateEnd, pair, uPnL, rPnL, side, entryPrice, initialSL, maxTP, idealTP, amount,
  amountClosed, status, day, tags, avgClosePrice, avgRiskReward, maxRiskReward, exchangeRate,
  initialBalance, currentRealizedBalance
Times are naive clock times in whatever timezone the FX Replay chart was set to. The caller passes
that zone and gets aware UTC datetimes back.
"""

import csv
import io
import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

KNOWN_COLUMNS = (
    "id",
    "dateStart",
    "dateEnd",
    "pair",
    "uPnL",
    "rPnL",
    "side",
    "entryPrice",
    "initialSL",
    "maxTP",
    "idealTP",
    "amount",
    "amountClosed",
    "status",
    "day",
    "tags",
    "avgClosePrice",
    "avgRiskReward",
    "maxRiskReward",
    "exchangeRate",
    "initialBalance",
    "currentRealizedBalance",
)
REQUIRED_COLUMNS = ("id", "dateStart", "dateEnd", "pair", "side", "entryPrice", "initialSL", "rPnL")

DATE_FORMATS = (
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
)

MAX_CSV_BYTES = 20 * 1024 * 1024
TAG_SEPARATORS = re.compile(r"[;,|]")


class CsvFormatError(Exception):
    pass


class RowError(Exception):
    pass


@dataclass
class ParsedRow:
    fx_id: str
    pair: str
    side: str
    opened_at: datetime  # aware, UTC
    closed_at: datetime | None
    entry_price: float
    initial_sl: float
    max_tp: float | None
    ideal_tp: float | None
    exit_price: float | None
    pnl: float
    avg_rr: float | None
    max_rr: float | None
    status: str
    tags: list[str]
    raw: dict[str, str]
    line: int


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)  # "line N: reason"
    unknown_columns: list[str] = field(default_factory=list)
    duplicate_in_file: list[str] = field(default_factory=list)
    timezone: str = "Europe/London"

    @property
    def total_rows(self) -> int:
        return len(self.rows) + len(self.problems) + len(self.duplicate_in_file)


def _float(value: str, column: str, *, required: bool) -> float | None:
    value = (value or "").strip()
    if value == "":
        if required:
            raise RowError(f"{column} is empty")
        return None
    try:
        number = float(value.replace(",", ""))
    except ValueError as exc:
        raise RowError(f"{column} '{value}' is not a number") from exc
    if not math.isfinite(number):
        raise RowError(f"{column} '{value}' is not a finite number")
    return number


def parse_clock(value: str, column: str) -> datetime:
    value = (value or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise RowError(f"{column} '{value}' is not a date we recognise")


def localise(naive: datetime, zone: ZoneInfo) -> datetime:
    """Attach the chart's zone and convert to UTC. fold=0 picks the first of an ambiguous DST hour."""
    return naive.replace(tzinfo=zone).astimezone(UTC)


def split_tags(value: str) -> list[str]:
    return [t.strip() for t in TAG_SEPARATORS.split(value or "") if t.strip()]


def resolve_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise CsvFormatError(f"Unknown timezone '{name}'.") from exc


def parse_csv(data: bytes | str, *, timezone: str = "Europe/London") -> ParseResult:
    if isinstance(data, bytes):
        if len(data) > MAX_CSV_BYTES:
            raise CsvFormatError("That file is over 20 MB. Is it really an FX Replay export?")
        text = data.decode("utf-8-sig", errors="replace")
    else:
        text = data.lstrip("﻿")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise CsvFormatError("The file is empty.")

    zone = resolve_zone(timezone)
    reader = csv.reader(io.StringIO(text))
    try:
        header = [h.strip().lstrip("﻿") for h in next(reader)]
    except StopIteration as exc:
        raise CsvFormatError("The file is empty.") from exc
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise CsvFormatError(
            f"Missing columns: {', '.join(missing)}. Is this an FX Replay trades export (Analytics → Export)?"
        )
    result = ParseResult(timezone=timezone, unknown_columns=[h for h in header if h not in KNOWN_COLUMNS])
    seen: set[str] = set()
    for line_no, values in enumerate(reader, start=2):
        if not any(v.strip() for v in values):
            continue
        row = {header[i]: (values[i].strip() if i < len(values) else "") for i in range(len(header))}
        try:
            parsed = _parse_row(row, line_no, zone)
        except RowError as exc:
            result.problems.append(f"line {line_no}: {exc}")
            continue
        if parsed.fx_id in seen:
            result.duplicate_in_file.append(parsed.fx_id)
            result.problems.append(f"line {line_no}: trade {parsed.fx_id} appears twice in the file")
            continue
        seen.add(parsed.fx_id)
        result.rows.append(parsed)
    return result


def _parse_row(row: dict[str, str], line: int, zone: ZoneInfo) -> ParsedRow:
    fx_id = row.get("id", "").strip()
    if not fx_id:
        raise RowError("id is empty")
    pair = row.get("pair", "").strip()
    if not pair:
        raise RowError("pair is empty")
    side = row.get("side", "").strip().lower()
    if side not in ("buy", "sell"):
        raise RowError(f"side '{row.get('side', '')}' should be buy or sell")
    opened = parse_clock(row["dateStart"], "dateStart")
    closed_raw = row.get("dateEnd", "").strip()
    closed = parse_clock(closed_raw, "dateEnd") if closed_raw else None
    if closed and closed < opened:
        raise RowError("dateEnd is before dateStart")
    status = (row.get("status") or "closed").strip().lower() or "closed"
    if status not in ("open", "closed"):
        raise RowError(f"status '{status}' should be open or closed")
    return ParsedRow(
        fx_id=fx_id,
        pair=pair,
        side=side,
        opened_at=localise(opened, zone),
        closed_at=localise(closed, zone) if closed else None,
        entry_price=_float(row["entryPrice"], "entryPrice", required=True),
        initial_sl=_float(row["initialSL"], "initialSL", required=True),
        max_tp=_float(row.get("maxTP", ""), "maxTP", required=False),
        ideal_tp=_float(row.get("idealTP", ""), "idealTP", required=False),
        exit_price=_float(row.get("avgClosePrice", ""), "avgClosePrice", required=False),
        pnl=_float(row["rPnL"], "rPnL", required=True),
        avg_rr=_float(row.get("avgRiskReward", ""), "avgRiskReward", required=False),
        max_rr=_float(row.get("maxRiskReward", ""), "maxRiskReward", required=False),
        status=status,
        tags=split_tags(row.get("tags", "")),
        raw=row,
        line=line,
    )


def realised_r(side: str, entry: float, sl: float, exit_price: float | None) -> float | None:
    risk = abs(entry - sl)
    if risk == 0 or exit_price is None:
        return None
    direction = 1 if side == "buy" else -1
    return direction * (exit_price - entry) / risk


def target_r(side: str, entry: float, sl: float, tp: float | None) -> float | None:
    risk = abs(entry - sl)
    if risk == 0 or tp is None:
        return None
    direction = 1 if side == "buy" else -1
    return direction * (tp - entry) / risk
