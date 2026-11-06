"""The metric registry (F16): one place that says what each number is, how it's worked out, and computes it.

Every metric has an id, a label, a unit, the formula text the UI shows as a tooltip, and a function of a
`Ctx` (the aggregates of one set of rows, built once). Functions return None when a number has no meaning
(no trades, no losses for a profit factor) rather than 0, so the UI can say why.

Conventions, matched to FX Replay where its docs say (docs/build/research/fxreplay-metrics.md):
- Win rate = wins ÷ (wins + losses). Breakevens (|P&L| ≤ threshold, default $2) are left out.
- P&L is booked at close: the equity curve, drawdown and streaks run in close order.
- Profit factor = gross profit of wins ÷ gross loss of losses. No losses → None ("undefined").
- Drawdown is peak-to-trough on the cumulative curve, starting from 0 before the first trade. Negative or 0.
- A breakeven ends a streak.
"""

import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from .rows import Row

Unit = Literal["count", "pct", "r", "usd", "duration", "ratio"]


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def max_drawdown(values: list[float]) -> float:
    """Largest peak-to-trough fall of the running total of `values`, starting from 0. Returned ≤ 0."""
    peak = total = 0.0
    worst = 0.0
    for v in values:
        total += v
        peak = max(peak, total)
        worst = min(worst, total - peak)
    return worst


def drawdown_series(values: list[float]) -> list[float]:
    """Drawdown from the running peak after each trade (≤ 0)."""
    peak = total = 0.0
    out = []
    for v in values:
        total += v
        peak = max(peak, total)
        out.append(total - peak)
    return out


def streaks(outcomes: list[str | None]) -> dict[str, list[int]]:
    """Runs of consecutive wins and losses in booking order. A breakeven (or no outcome) ends a run."""
    runs: dict[str, list[int]] = {"win": [], "loss": []}
    current, length = None, 0
    for o in outcomes + [None]:
        if o == current and o in runs:
            length += 1
            continue
        if current in runs and length:
            runs[current].append(length)
        current, length = o, 1
    return runs


@dataclass
class Ctx:
    """Aggregates of one set of rows (already classified and in booking order)."""

    rows: list[Row]
    wins: list[Row] = field(default_factory=list)
    losses: list[Row] = field(default_factory=list)
    breakevens: list[Row] = field(default_factory=list)
    rs: list[float] = field(default_factory=list)  # realised R, booking order, trades with an R
    pnls: list[float] = field(default_factory=list)  # P&L, booking order, trades with a P&L
    runs: dict[str, list[int]] = field(default_factory=dict)

    @classmethod
    def build(cls, rows: list[Row]) -> "Ctx":
        ctx = cls(rows=rows)
        for r in rows:
            if r.outcome == "win":
                ctx.wins.append(r)
            elif r.outcome == "loss":
                ctx.losses.append(r)
            elif r.outcome == "breakeven":
                ctx.breakevens.append(r)
            if r.r is not None:
                ctx.rs.append(r.r)
            if r.pnl is not None:
                ctx.pnls.append(r.pnl)
        ctx.runs = streaks([r.outcome for r in rows])
        return ctx

    @property
    def decided(self) -> int:
        return len(self.wins) + len(self.losses)

    def win_r(self) -> list[float]:
        return [r.r for r in self.wins if r.r is not None]

    def loss_r(self) -> list[float]:
        return [r.r for r in self.losses if r.r is not None]

    def win_pnl(self) -> list[float]:
        return [r.pnl for r in self.wins if r.pnl is not None]

    def loss_pnl(self) -> list[float]:
        return [r.pnl for r in self.losses if r.pnl is not None]


# ---- metric functions ----------------------------------------------------------------------------


def win_rate(c: Ctx) -> float | None:
    return len(c.wins) / c.decided if c.decided else None


def net_pnl(c: Ctx) -> float | None:
    return sum(c.pnls) if c.pnls else None


def total_r(c: Ctx) -> float | None:
    return sum(c.rs) if c.rs else None


def avg_r(c: Ctx) -> float | None:
    return _mean(c.rs)


def _expectancy(c: Ctx, wins: list[float], losses: list[float]) -> float | None:
    wr = win_rate(c)
    if wr is None:
        return None
    avg_win = _mean(wins) or 0.0
    avg_loss = abs(_mean(losses) or 0.0)
    return wr * avg_win - (1 - wr) * avg_loss


def expectancy_r(c: Ctx) -> float | None:
    return _expectancy(c, c.win_r(), c.loss_r())


def expectancy_pnl(c: Ctx) -> float | None:
    return _expectancy(c, c.win_pnl(), c.loss_pnl())


def avg_win_r(c: Ctx) -> float | None:
    return _mean(c.win_r())


def avg_loss_r(c: Ctx) -> float | None:
    return _mean(c.loss_r())


def avg_win_pnl(c: Ctx) -> float | None:
    return _mean(c.win_pnl())


def avg_loss_pnl(c: Ctx) -> float | None:
    return _mean(c.loss_pnl())


def _profit_factor(wins: list[float], losses: list[float]) -> float | None:
    gross_loss = -sum(losses)
    if gross_loss <= 0:
        return None
    return sum(wins) / gross_loss


def profit_factor(c: Ctx) -> float | None:
    return _profit_factor(c.win_pnl(), c.loss_pnl())


def profit_factor_r(c: Ctx) -> float | None:
    return _profit_factor(c.win_r(), c.loss_r())


def max_dd_r(c: Ctx) -> float | None:
    return max_drawdown(c.rs) if c.rs else None


def max_dd_pnl(c: Ctx) -> float | None:
    return max_drawdown(c.pnls) if c.pnls else None


def longest_win_streak(c: Ctx) -> float | None:
    return float(max(c.runs.get("win") or [0])) if c.rows else None


def longest_loss_streak(c: Ctx) -> float | None:
    return float(max(c.runs.get("loss") or [0])) if c.rows else None


def best_r(c: Ctx) -> float | None:
    return max(c.rs) if c.rs else None


def worst_r(c: Ctx) -> float | None:
    return min(c.rs) if c.rs else None


def best_pnl(c: Ctx) -> float | None:
    return max(c.pnls) if c.pnls else None


def worst_pnl(c: Ctx) -> float | None:
    return min(c.pnls) if c.pnls else None


def max_win_r(c: Ctx) -> float | None:
    rs = c.win_r()
    return max(rs) if rs else None


def avg_duration(c: Ctx) -> float | None:
    return _mean([float(r.duration_seconds) for r in c.rows if r.duration_seconds is not None])


def avg_win_duration(c: Ctx) -> float | None:
    return _mean([float(r.duration_seconds) for r in c.wins if r.duration_seconds is not None])


def avg_loss_duration(c: Ctx) -> float | None:
    return _mean([float(r.duration_seconds) for r in c.losses if r.duration_seconds is not None])


def rules_kept_rate(c: Ctx) -> float | None:
    marked = [r.rules_kept for r in c.rows if r.rules_kept is not None]
    return sum(marked) / len(marked) if marked else None


def _excursion_rows(c: Ctx) -> list[Row]:
    return [r for r in c.rows if r.mfe_r is not None and r.mfe_r > 0 and r.r is not None]


def exit_efficiency(c: Ctx) -> float | None:
    """Σ max(R, 0) ÷ Σ MFE over trades with a favourable excursion (U10)."""
    rows = _excursion_rows(c)
    offered = sum(r.mfe_r for r in rows)  # type: ignore[misc]
    if not rows or offered <= 0:
        return None
    return sum(max(r.r, 0.0) for r in rows) / offered  # type: ignore[arg-type]


def r_left_on_table(c: Ctx) -> float | None:
    rows = _excursion_rows(c)
    return _mean([max(0.0, r.mfe_r - r.r) for r in rows])  # type: ignore[operator]


def avg_winner_mae(c: Ctx) -> float | None:
    """FX Replay's 'drawdown': how far price went against a winner before it closed, in R."""
    return _mean([abs(r.mae_r) for r in c.wins if r.mae_r is not None])


def avg_tp_r(c: Ctx) -> float | None:
    return _mean([r.tp_r for r in c.rows if r.tp_r is not None])


def avg_sl_distance(c: Ctx) -> float | None:
    return _mean([r.sl_distance for r in c.rows if r.sl_distance is not None])


def avg_tp_distance(c: Ctx) -> float | None:
    return _mean([r.tp_distance for r in c.rows if r.tp_distance is not None])


def median_duration(c: Ctx) -> float | None:
    return _median([float(r.duration_seconds) for r in c.rows if r.duration_seconds is not None])


# ---- the registry --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Metric:
    id: str
    label: str
    unit: Unit
    formula: str
    fn: Callable[[Ctx], float | None]
    better: Literal["higher", "lower", "neutral"] = "higher"
    sources: tuple[str, ...] = ("backtest",)

    def meta(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "unit": self.unit,
            "formula": self.formula,
            "better": self.better,
            "sources": list(self.sources),
        }


def _count(attr: str) -> Callable[[Ctx], float | None]:
    return lambda c: float(len(getattr(c, attr)))


B, IDEAL, BOTH = ("backtest",), ("ideal",), ("backtest", "ideal")

REGISTRY: tuple[Metric, ...] = (
    Metric(
        "trades",
        "Trades",
        "count",
        "Every trade in the filter, wins, losses and breakevens.",
        lambda c: float(len(c.rows)),
        "neutral",
        BOTH,
    ),
    Metric("wins", "Wins", "count", "P&L above the breakeven threshold.", _count("wins"), "neutral"),
    Metric(
        "losses", "Losses", "count", "P&L below minus the breakeven threshold.", _count("losses"), "neutral"
    ),
    Metric(
        "breakevens",
        "Breakevens",
        "count",
        "P&L within ± the breakeven threshold (default $2).",
        _count("breakevens"),
        "neutral",
    ),
    Metric(
        "win_rate",
        "Win rate",
        "pct",
        "Wins ÷ (wins + losses). Breakevens are left out, as FX Replay does.",
        win_rate,
    ),
    Metric("net_pnl", "Net P&L", "usd", "Sum of every trade's realised P&L (FX Replay's rPnL).", net_pnl),
    Metric("total_r", "Total R", "r", "Sum of every trade's realised R.", total_r),
    Metric(
        "avg_r", "Average R", "r", "Total R ÷ trades with an R (breakevens included).", avg_r, sources=BOTH
    ),
    Metric(
        "expectancy_r",
        "Expectancy",
        "r",
        "Win rate × average win R − (1 − win rate) × |average loss R|.",
        expectancy_r,
    ),
    Metric(
        "expectancy_pnl",
        "Expectancy ($)",
        "usd",
        "Win rate × average win $ − (1 − win rate) × |average loss $|.",
        expectancy_pnl,
    ),
    Metric(
        "profit_factor",
        "Profit factor",
        "ratio",
        "Gross profit of wins ÷ gross loss of losses, in $. No losses: undefined.",
        profit_factor,
    ),
    Metric(
        "profit_factor_r",
        "Profit factor (R)",
        "ratio",
        "Total R of wins ÷ |total R of losses|. No losses: undefined.",
        profit_factor_r,
    ),
    Metric("avg_win_r", "Average win", "r", "Mean R of winning trades (FX Replay's Average RR).", avg_win_r),
    Metric("avg_loss_r", "Average loss", "r", "Mean R of losing trades.", avg_loss_r, "neutral"),
    Metric("avg_win_pnl", "Average win ($)", "usd", "Mean P&L of winning trades.", avg_win_pnl),
    Metric("avg_loss_pnl", "Average loss ($)", "usd", "Mean P&L of losing trades.", avg_loss_pnl, "neutral"),
    Metric(
        "max_dd_r",
        "Max drawdown",
        "r",
        "Largest fall from a peak of cumulative R, trades booked at close, starting from 0.",
        max_dd_r,
    ),
    Metric(
        "max_dd_pnl",
        "Max drawdown ($)",
        "usd",
        "Largest fall from a peak of cumulative P&L, trades booked at close, starting from 0.",
        max_dd_pnl,
    ),
    Metric(
        "longest_win_streak",
        "Longest win streak",
        "count",
        "Most wins in a row, in close order. A breakeven ends a streak.",
        longest_win_streak,
    ),
    Metric(
        "longest_loss_streak",
        "Longest loss streak",
        "count",
        "Most losses in a row, in close order. A breakeven ends a streak.",
        longest_loss_streak,
        "lower",
    ),
    Metric("best_r", "Best trade", "r", "Highest realised R.", best_r, "neutral"),
    Metric("worst_r", "Worst trade", "r", "Lowest realised R.", worst_r, "neutral"),
    Metric("best_pnl", "Best trade ($)", "usd", "Highest realised P&L.", best_pnl, "neutral"),
    Metric("worst_pnl", "Worst trade ($)", "usd", "Lowest realised P&L.", worst_pnl, "neutral"),
    Metric(
        "max_win_r", "Max RR", "r", "Highest R on a winning trade (FX Replay's Max RR).", max_win_r, "neutral"
    ),
    Metric(
        "avg_duration",
        "Average duration",
        "duration",
        "Mean time from open to close.",
        avg_duration,
        "neutral",
        BOTH,
    ),
    Metric(
        "avg_win_duration",
        "Average duration (wins)",
        "duration",
        "Mean time held on winners.",
        avg_win_duration,
        "neutral",
    ),
    Metric(
        "avg_loss_duration",
        "Average duration (losses)",
        "duration",
        "Mean time held on losers.",
        avg_loss_duration,
        "neutral",
    ),
    Metric(
        "rules_kept_rate",
        "Rules kept",
        "pct",
        "Trades with every rulebook box ticked ÷ trades with the rulebook filled in.",
        rules_kept_rate,
    ),
    Metric(
        "exit_efficiency",
        "Exit efficiency",
        "pct",
        "Σ max(R, 0) ÷ Σ max favourable R, over trades with MFE (entered, or FX Replay's ideal price).",
        exit_efficiency,
    ),
    Metric(
        "r_left_on_table",
        "R left on the table",
        "r",
        "Mean of (max favourable R − realised R) over trades with MFE.",
        r_left_on_table,
        "lower",
    ),
    Metric(
        "avg_winner_mae",
        "Winner drawdown",
        "r",
        "Mean adverse excursion of winners before they closed, in R (FX Replay's Drawdown tab).",
        avg_winner_mae,
        "lower",
    ),
    Metric(
        "avg_tp_r",
        "Average target",
        "r",
        "Mean distance to the take-profit, in R.",
        avg_tp_r,
        "neutral",
        IDEAL,
    ),
    Metric(
        "avg_sl_distance",
        "Average stop",
        "count",
        "Mean stop distance in pips or points.",
        avg_sl_distance,
        "neutral",
        BOTH,
    ),
    Metric(
        "avg_tp_distance",
        "Average target distance",
        "count",
        "Mean target distance in pips or points.",
        avg_tp_distance,
        "neutral",
        IDEAL,
    ),
    Metric(
        "median_duration",
        "Typical duration",
        "duration",
        "Median time from open to close.",
        median_duration,
        "neutral",
        IDEAL,
    ),
)

BY_ID = {m.id: m for m in REGISTRY}


def compute(rows: list[Row], source: str = "backtest", ctx: Ctx | None = None) -> dict[str, float | None]:
    """Every metric that applies to `source`, rounded for the wire (4 dp; counts as ints)."""
    ctx = ctx or Ctx.build(rows)
    out: dict[str, float | None] = {}
    for m in REGISTRY:
        if source not in m.sources:
            continue
        value = m.fn(ctx)
        if value is None:
            out[m.id] = None
        elif m.unit == "count" and float(value).is_integer():
            out[m.id] = int(value)
        else:
            out[m.id] = round(value, 4)
    return out


def registry_meta(source: str | None = None) -> list[dict]:
    return [m.meta() for m in REGISTRY if source is None or source in m.sources or source == "compare"]
