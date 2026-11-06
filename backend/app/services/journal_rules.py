"""The Replay Journal's rules in one place: coverage, unlock, breakeven, UK sessions (F9, F16).

Change a threshold here and every screen, stat and test follows.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

UK_TZ = ZoneInfo("Europe/London")

COVERAGE_MONTHS = 6  # consecutive covered months needed to unlock the Backtest tab
MIN_UNLOCK_TRADES = 6  # implied by 1+ trade per month; kept explicit so the rule reads in one line
DEFAULT_BREAKEVEN_THRESHOLD = 10.0  # account currency ($); |P&L| <= threshold is breakeven (Jamie, 6 Nov)

# UK session windows (start inclusive, end exclusive) in minutes from midnight, UK local time.
SESSION_WINDOWS: tuple[tuple[str, int, int], ...] = (
    ("Asia", 0, 8 * 60),
    ("London", 8 * 60, 13 * 60),
    ("New York", 13 * 60, 22 * 60),
)


def classify_outcome(pnl: float | None, threshold: float = DEFAULT_BREAKEVEN_THRESHOLD) -> str | None:
    """win above +threshold, loss below -threshold, breakeven in between (inclusive)."""
    if pnl is None:
        return None
    if pnl > threshold:
        return "win"
    if pnl < -threshold:
        return "loss"
    return "breakeven"


def to_uk(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UK_TZ)


def market_date(opened_at: datetime) -> date:
    """The trade's date in UK time, which is what coverage counts."""
    return to_uk(opened_at).date()


def session_label(opened_at: datetime) -> str:
    uk = to_uk(opened_at)
    minute = uk.hour * 60 + uk.minute
    for name, start, end in SESSION_WINDOWS:
        if start <= minute < end:
            return name
    return "Out of session"


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _add_months(year: int, month: int, n: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + n
    return idx // 12, idx % 12 + 1


@dataclass(frozen=True)
class Coverage:
    months: list[dict]  # [{month: "2026-03", trades: n, covered: bool}] oldest first, gaps included
    covered_count: int  # months with >= 1 trade
    best_run: int  # longest run of consecutive covered months
    current_run: int  # run ending at the most recent covered month
    trade_count: int
    unlocked: bool
    first_month: str | None
    last_month: str | None
    next_uncovered: str | None  # the first gap after the latest covered month run, or the month after it

    @property
    def progress(self) -> float:
        return min(1.0, self.best_run / COVERAGE_MONTHS)


def coverage(opened_ats: Iterable[datetime]) -> Coverage:
    """Coverage from the open times of the live (non-deleted) ideal trades.

    A month is covered when it holds at least one trade by the trade's UK open date. Unlock needs
    COVERAGE_MONTHS consecutive covered months and at least MIN_UNLOCK_TRADES trades.
    """
    counts: dict[tuple[int, int], int] = {}
    total = 0
    for moment in opened_ats:
        d = market_date(moment)
        counts[(d.year, d.month)] = counts.get((d.year, d.month), 0) + 1
        total += 1
    if not counts:
        return Coverage([], 0, 0, 0, 0, False, None, None, None)
    first, last = min(counts), max(counts)
    months: list[dict] = []
    y, m = first
    best = run = 0
    last_gap: str | None = None
    while (y, m) <= last:
        n = counts.get((y, m), 0)
        months.append({"month": f"{y:04d}-{m:02d}", "trades": n, "covered": n > 0})
        if n > 0:
            run += 1
            best = max(best, run)
        else:
            run = 0
            last_gap = f"{y:04d}-{m:02d}"
        y, m = _add_months(y, m, 1)
    if last_gap:
        # Filling the most recent gap joins the current run to the one before it: the best next replay.
        next_uncovered = last_gap
    else:
        ny, nm = _add_months(last[0], last[1], 1)
        next_uncovered = f"{ny:04d}-{nm:02d}"
    unlocked = best >= COVERAGE_MONTHS and total >= MIN_UNLOCK_TRADES
    return Coverage(
        months=months,
        covered_count=sum(1 for mo in months if mo["covered"]),
        best_run=best,
        current_run=run,
        trade_count=total,
        unlocked=unlocked,
        first_month=months[0]["month"],
        last_month=months[-1]["month"],
        next_uncovered=next_uncovered if not unlocked else None,
    )


def stage(cov: Coverage, backtest_trades: int) -> str:
    """Ideal Trades → Ready to backtest → Backtesting."""
    if backtest_trades > 0:
        return "backtesting"
    if cov.unlocked:
        return "ready"
    return "ideal"
