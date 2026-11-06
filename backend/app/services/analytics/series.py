"""Breakdowns, distributions, the equity curve, the P&L calendar, the rulebook and Compare.

Pure functions over prepared `Row` lists (classified, booking order). Every group carries its own n so the
UI can say how much a bar stands on.
"""

import math
from collections import defaultdict
from collections.abc import Callable, Iterable

from .metrics import Ctx, _mean, avg_r, drawdown_series, profit_factor, total_r, win_rate
from .rows import WEEKDAYS, Row

SESSION_ORDER = ("Asia", "London", "New York", "Out of session")


def _r2(v: float | None, dp: int = 4) -> float | None:
    return None if v is None else round(v, dp)


def group_stats(rows: list[Row]) -> dict:
    c = Ctx.build(rows)
    return {
        "n": len(rows),
        "wins": len(c.wins),
        "losses": len(c.losses),
        "breakevens": len(c.breakevens),
        "win_rate": _r2(win_rate(c)),
        "total_r": _r2(total_r(c)),
        "avg_r": _r2(avg_r(c)),
        "pnl": _r2(sum(c.pnls), 2) if c.pnls else None,
        "profit_factor": _r2(profit_factor(c)),
        "avg_sl": _r2(_mean([r.sl_distance for r in rows if r.sl_distance is not None]), 2),
        "avg_tp_r": _r2(_mean([r.tp_r for r in rows if r.tp_r is not None])),
        "avg_duration": _r2(
            _mean([float(r.duration_seconds) for r in rows if r.duration_seconds is not None]), 0
        ),
    }


def breakdown(
    rows: list[Row], key: Callable[[Row], str | None], order: Iterable[str] | None = None, *, keep_empty=False
) -> list[dict]:
    groups: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        k = key(r)
        groups[k if k else "Not set"].append(r)
    labels = list(order or [])
    if keep_empty:
        keys = labels + [k for k in groups if k not in labels]
    else:
        keys = [k for k in labels if k in groups] + sorted(
            (k for k in groups if k not in labels), key=lambda k: (-len(groups[k]), k)
        )
    return [{"key": k, "label": k, **group_stats(groups.get(k, []))} for k in keys]


def breakdowns(rows: list[Row]) -> dict[str, list[dict]]:
    weekdays_seen = {r.weekday for r in rows}
    weekday_order = [d for i, d in enumerate(WEEKDAYS) if i < 5 or i in weekdays_seen]
    return {
        "hour": breakdown(rows, lambda r: f"{r.hour:02d}:00", [f"{h:02d}:00" for h in range(24)]),
        "weekday": breakdown(rows, lambda r: WEEKDAYS[r.weekday], weekday_order, keep_empty=True),
        "session": breakdown(rows, lambda r: r.session_label or None, SESSION_ORDER),
        "entry_model": breakdown(rows, lambda r: r.entry_model),
        "instrument": breakdown(rows, lambda r: r.instrument),
        "direction": breakdown(rows, lambda r: "Long" if r.side == "buy" else "Short", ("Long", "Short")),
    }


NEWS_GROUPS = (("inside", "Inside news window"), ("outside", "Outside"), ("no_data", "No news data"))


def around_news(rows: list[Row]) -> list[dict]:
    """3.6 "Around news": inside vs outside the news windows vs no data, then each event type (a trade
    inside two events' windows counts under both)."""

    def stats(key: str, group: list[Row]) -> dict:
        g = group_stats(group)
        return {
            "key": key,
            "trades": g["n"],
            "win_rate": g["win_rate"],
            "avg_r": g["avg_r"],
            "total_r": g["total_r"],
        }

    out = [stats(label, [r for r in rows if r.news_status == status]) for status, label in NEWS_GROUPS]
    by_type: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        for name in dict.fromkeys(r.news_events):
            by_type[name].append(r)
    for name in sorted(by_type, key=lambda k: (-len(by_type[k]), k)):
        out.append(stats(name, by_type[name]))
    return out


def equity(rows: list[Row]) -> list[dict]:
    """Cumulative R and P&L in booking order, with the drawdown at each point."""
    rs = [r.r or 0.0 for r in rows]
    pnls = [r.pnl or 0.0 for r in rows]
    dd_r = drawdown_series(rs)
    dd_p = drawdown_series(pnls)
    out, cum_r, cum_p = [], 0.0, 0.0
    for i, (row, r, p) in enumerate(zip(rows, rs, pnls, strict=True)):
        cum_r += r
        cum_p += p
        out.append(
            {
                "i": i + 1,
                "id": row.id,
                "at": row.booked_at.isoformat(),
                "r": _r2(row.r),
                "pnl": _r2(row.pnl, 2),
                "outcome": row.outcome,
                "cum_r": round(cum_r, 4),
                "cum_pnl": round(cum_p, 2),
                "dd_r": round(dd_r[i], 4),
                "dd_pnl": round(dd_p[i], 2),
            }
        )
    return out


def streak_runs(rows: list[Row]) -> list[dict]:
    """Every run of wins or losses with where it started, for the streak strip."""
    out: list[dict] = []
    for row in rows:
        o = row.outcome
        if out and out[-1]["outcome"] == o:
            out[-1]["length"] += 1
            out[-1]["r"] = round(out[-1]["r"] + (row.r or 0.0), 4)
        else:
            out.append(
                {"outcome": o, "length": 1, "start": row.booked_at.isoformat(), "r": round(row.r or 0.0, 4)}
            )
    return out


def calendar(rows: list[Row]) -> list[dict]:
    """Daily P&L by the UK date of the open (FX Replay's calendar uses the open)."""
    days: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        days[r.market_date.isoformat()].append(r)  # type: ignore[union-attr]
    out = []
    for day in sorted(days):
        rs = days[day]
        c = Ctx.build(rs)
        out.append(
            {
                "date": day,
                "n": len(rs),
                "wins": len(c.wins),
                "losses": len(c.losses),
                "pnl": round(sum(c.pnls), 2) if c.pnls else None,
                "r": round(sum(c.rs), 4) if c.rs else None,
            }
        )
    return out


def heatmap(rows: list[Row]) -> list[dict]:
    """Entry time (UK hour) × weekday: count and average R per cell."""
    cells: dict[tuple[int, int], list[Row]] = defaultdict(list)
    for r in rows:
        cells[(r.weekday, r.hour)].append(r)
    return [
        {
            "weekday": wd,
            "hour": h,
            "n": len(rs),
            "avg_r": _r2(_mean([x.r for x in rs if x.r is not None])),
        }
        for (wd, h), rs in sorted(cells.items())
    ]


def histogram(
    values: list[float], width: float, *, max_bins: int = 40, floor_at: float | None = None
) -> list[dict]:
    """Fixed-width bins from floor(min) to ceil(max). Widens the bin if there would be too many."""
    values = [v for v in values if math.isfinite(v)]
    if not values:
        return []
    lo = math.floor(min(values) / width) * width
    if floor_at is not None:
        lo = max(lo, floor_at)
    hi = max(values)
    for _ in range(64):  # bounded: each pass doubles the width
        if (hi - lo) / width + 1 <= max_bins:
            break
        width *= 2
        lo = math.floor(min(values) / width) * width
    if (hi - lo) / width + 1 > max_bins:  # absurd spreads: fall back to exactly max_bins bins
        width = (hi - lo) / (max_bins - 1) or 1.0
    n_bins = int((hi - lo) // width) + 1
    counts = [0] * n_bins
    for v in values:
        idx = min(n_bins - 1, max(0, int((v - lo) // width)))
        counts[idx] += 1
    return [
        {"from": round(lo + i * width, 4), "to": round(lo + (i + 1) * width, 4), "n": counts[i]}
        for i in range(n_bins)
    ]


DURATION_BUCKETS = (
    ("< 15 min", 0, 15 * 60),
    ("15–30 min", 15 * 60, 30 * 60),
    ("30–60 min", 30 * 60, 3600),
    ("1–2 h", 3600, 2 * 3600),
    ("2–4 h", 2 * 3600, 4 * 3600),
    ("4–8 h", 4 * 3600, 8 * 3600),
    ("8–24 h", 8 * 3600, 24 * 3600),
    ("1–2 d", 24 * 3600, 48 * 3600),
    ("2 d +", 48 * 3600, math.inf),
)


def duration_histogram(rows: list[Row]) -> list[dict]:
    out = []
    for label, lo, hi in DURATION_BUCKETS:
        out.append(
            {
                "label": label,
                "n": sum(1 for r in rows if r.duration_seconds is not None and lo <= r.duration_seconds < hi),
            }
        )
    return out


def r_distribution(rows: list[Row]) -> list[dict]:
    return histogram([r.r for r in rows if r.r is not None], 0.5)


def ideal_distributions(rows: list[Row]) -> dict:
    sl = [r.sl_distance for r in rows if r.sl_distance is not None]
    tp = [r.tp_distance for r in rows if r.tp_distance is not None]
    span = max(sl + tp, default=0)
    width = 10 ** max(0, math.floor(math.log10(span / 8))) if span > 8 else 1
    return {
        "tp_r": histogram([r.tp_r for r in rows if r.tp_r is not None], 0.5),
        "sl_distance": histogram(sl, width, floor_at=0),
        "tp_distance": histogram(tp, width, floor_at=0),
        "duration": duration_histogram(rows),
    }


def rulebook(rows: list[Row], rules: list[dict] | None = None) -> dict:
    """U9: R with all rules kept vs any broken, and what each broken rule cost.

    cost_r = trades that broke the rule × (average R when it was kept − average R when it was broken).
    """
    marked = [r for r in rows if r.rules]
    kept = [r for r in marked if r.rules_kept]
    broken = [r for r in marked if not r.rules_kept]
    labels = {r["key"]: r["text"] for r in rules or []}
    keys = list(labels) + sorted({k for r in marked for k in r.rules} - set(labels))
    per_rule = []
    for k in keys:
        with_rule = [r for r in marked if k in r.rules]
        k_kept = [r.r for r in with_rule if r.rules[k] and r.r is not None]
        k_broken = [r.r for r in with_rule if not r.rules[k] and r.r is not None]
        avg_k, avg_b = _mean(k_kept), _mean(k_broken)
        per_rule.append(
            {
                "key": k,
                "text": labels.get(k, k),
                "kept": len(k_kept),
                "broken": len(k_broken),
                "avg_r_kept": _r2(avg_k),
                "avg_r_broken": _r2(avg_b),
                "cost_r": _r2(len(k_broken) * (avg_k - avg_b))
                if avg_k is not None and avg_b is not None
                else None,
            }
        )
    return {
        "marked": len(marked),
        "all_kept": group_stats(kept),
        "any_broken": group_stats(broken),
        "rules": per_rule,
    }


def excursions(rows: list[Row]) -> dict:
    """U10 scatter: realised R against max favourable R, per trade."""
    pts = [r for r in rows if r.mfe_r is not None and r.r is not None]
    return {
        "n": len(pts),
        "points": [
            {"id": r.id, "r": round(r.r, 4), "mfe": round(r.mfe_r, 4), "outcome": r.outcome} for r in pts
        ],  # type: ignore[arg-type]
    }


def compare(ideal: list[Row], backtest: list[Row]) -> dict:
    """The backtest's results set against the ideal profile (2.4 Compare)."""
    ci, cb = Ctx.build(ideal), Ctx.build(backtest)
    ideal_avg = avg_r(ci)
    bt_win = _mean(cb.win_r())
    bt_avg = avg_r(cb)

    def capture(v: float | None) -> float | None:
        return _r2(v / ideal_avg) if v is not None and ideal_avg else None

    def side_by_side(key: Callable[[Row], str | None], order: Iterable[str] | None = None) -> list[dict]:
        ideal_groups = {g["key"]: g for g in breakdown(ideal, key, order)}
        bt_groups = {g["key"]: g for g in breakdown(backtest, key, order)}
        keys = [k for k in (order or []) if k in ideal_groups or k in bt_groups]
        keys += sorted((set(ideal_groups) | set(bt_groups)) - set(keys))
        out = []
        for k in keys:
            ig, bg = ideal_groups.get(k), bt_groups.get(k)
            holds = None
            if bg and bg["n"] >= 3 and bg["avg_r"] is not None:
                holds = "holds" if bg["avg_r"] > 0 else "fails"
            out.append(
                {
                    "key": k,
                    "ideal_n": ig["n"] if ig else 0,
                    "ideal_share": _r2(ig["n"] / len(ideal)) if ig and ideal else 0,
                    "ideal_avg_r": ig["avg_r"] if ig else None,
                    "backtest_n": bg["n"] if bg else 0,
                    "backtest_win_rate": bg["win_rate"] if bg else None,
                    "backtest_avg_r": bg["avg_r"] if bg else None,
                    "holds": holds,
                }
            )
        return out

    return {
        "ideal_n": len(ideal),
        "backtest_n": len(backtest),
        "ideal_avg_r": _r2(ideal_avg),
        "backtest_avg_win_r": _r2(bt_win),
        "backtest_avg_r": _r2(bt_avg),
        "capture_winners": capture(bt_win),
        "capture_all": capture(bt_avg),
        "ideal_avg_sl": _r2(_mean([r.sl_distance for r in ideal if r.sl_distance is not None]), 2),
        "backtest_avg_sl": _r2(_mean([r.sl_distance for r in backtest if r.sl_distance is not None]), 2),
        "ideal_avg_tp_r": _r2(_mean([r.tp_r for r in ideal if r.tp_r is not None])),
        "backtest_avg_tp_r": _r2(_mean([r.tp_r for r in backtest if r.tp_r is not None])),
        "by_hour": side_by_side(lambda r: f"{r.hour:02d}:00", [f"{h:02d}:00" for h in range(24)]),
        "by_entry_model": side_by_side(lambda r: r.entry_model),
        "by_session": side_by_side(lambda r: r.session_label or None, SESSION_ORDER),
        "by_weekday": side_by_side(lambda r: WEEKDAYS[r.weekday], WEEKDAYS),
    }


def by_owner(rows: list[Row]) -> dict[int, list[Row]]:
    groups: dict[int, list[Row]] = defaultdict(list)
    for r in rows:
        groups[r.owner_id].append(r)
    return dict(groups)
