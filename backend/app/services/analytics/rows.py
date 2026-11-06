"""The flat trade row every metric reads. Built once per query; no ORM objects past this point."""

from dataclasses import dataclass, field
from datetime import date, datetime

from ..journal_rules import DEFAULT_BREAKEVEN_THRESHOLD, classify_outcome, to_uk

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(slots=True)
class Row:
    id: int
    kind: str  # ideal | backtest
    opened_at: datetime  # aware UTC
    instrument: str = "NAS100"
    side: str = "buy"
    owner_id: int = 1
    strategy_id: int = 1
    session_id: int | None = None
    closed_at: datetime | None = None
    r: float | None = None
    pnl: float | None = None
    outcome: str | None = None  # win | loss | breakeven (set by `classify`)
    entry_model: str | None = None
    session_label: str = ""
    duration_seconds: int | None = None
    tags: tuple[str, ...] = ()
    tag_ids: frozenset[int] = frozenset()
    rules: dict[str, bool] = field(default_factory=dict)
    mae_r: float | None = None
    mfe_r: float | None = None  # entered by hand, or FX Replay's ideal price as R
    sl_distance: float | None = None
    tp_distance: float | None = None
    tp_r: float | None = None
    news_impact: str | None = None
    market_date: date | None = None  # UK date of the open
    uk_minute: int = 0  # minutes after UK midnight at the open
    weekday: int = 0  # 0 = Monday, UK

    def __post_init__(self) -> None:
        uk = to_uk(self.opened_at)
        if self.market_date is None:
            self.market_date = uk.date()
        self.uk_minute = uk.hour * 60 + uk.minute
        self.weekday = uk.weekday()

    @property
    def hour(self) -> int:
        return self.uk_minute // 60

    @property
    def booked_at(self) -> datetime:
        """P&L is booked at close (FX Replay and the old app agree); open trades book at the open."""
        return self.closed_at or self.opened_at

    @property
    def rules_kept(self) -> bool | None:
        if not self.rules:
            return None
        return all(bool(v) for v in self.rules.values())


def classify(row: Row, threshold: float = DEFAULT_BREAKEVEN_THRESHOLD) -> str | None:
    """One breakeven rule everywhere: P&L within ±threshold ($) is breakeven.

    Trades without a P&L (logged by hand with only an R) fall back to the stored outcome, then the sign of R.
    """
    if row.pnl is not None:
        return classify_outcome(row.pnl, threshold)
    if row.outcome:
        return row.outcome
    if row.r is None:
        return None
    return "win" if row.r > 0 else "loss" if row.r < 0 else "breakeven"


def prepare(rows: list[Row], threshold: float = DEFAULT_BREAKEVEN_THRESHOLD) -> list[Row]:
    """Classify outcomes with the viewer's threshold and sort by booking time (close, then id)."""
    for row in rows:
        row.outcome = classify(row, threshold)
    rows.sort(key=lambda r: (r.booked_at, r.id))
    return rows
