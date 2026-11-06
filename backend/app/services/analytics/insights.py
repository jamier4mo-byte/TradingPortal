"""Auto-insights (U11): the top differences between a slice of trades and the strategy's baseline.

Plain Python over the query's rows; no background job. A slice needs at least MIN_SLICE trades to be
considered, and anything under SOLID_SLICE is labelled "early signal".
"""

import math
from collections import defaultdict
from collections.abc import Callable

from .metrics import Ctx, _mean, avg_r, win_rate
from .rows import WEEKDAYS, Row

MIN_SLICE = 8
SOLID_SLICE = 20
MIN_EFFECT = 0.15  # 15% relative difference before something is worth saying

WEEKDAY_PLURAL = ("Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays")

DIMENSIONS: tuple[tuple[str, Callable[[Row], str | None], Callable[[str], str]], ...] = (
    ("weekday", lambda r: WEEKDAYS[r.weekday], lambda k: WEEKDAY_PLURAL[WEEKDAYS.index(k)]),
    ("session", lambda r: r.session_label or None, lambda k: f"{k} session" if k != "Out of session" else k),
    ("entry_model", lambda r: r.entry_model, lambda k: f"{k} entries"),
    ("hour", lambda r: f"{r.hour:02d}:00", lambda k: f"Entries at {k}"),
    (
        "direction",
        lambda r: "Long" if r.side == "buy" else "Short",
        lambda k: "Longs" if k == "Long" else "Shorts",
    ),
    ("instrument", lambda r: r.instrument, lambda k: k),
)


def _pct(v: float) -> str:
    return f"{round(abs(v) * 100)}%"


def _r(v: float) -> str:
    sign = "+" if v > 0 else "−" if v < 0 else ""
    return f"{sign}{abs(v):.2f}R"


def _measures(rows: list[Row], source: str) -> dict[str, float | None]:
    c = Ctx.build(rows)
    out = {
        "sl": _mean([r.sl_distance for r in rows if r.sl_distance is not None]),
        "tp_r": _mean([r.tp_r for r in rows if r.tp_r is not None]),
        "duration": _mean([float(r.duration_seconds) for r in rows if r.duration_seconds]),
    }
    if source == "backtest":
        out["win_rate"] = win_rate(c)
        out["avg_r"] = avg_r(c)
    return out


def _describe(metric: str, s: float, b: float) -> tuple[float, str] | None:
    """Relative effect and the phrase for one measure, or None if it's too small to mention."""
    if metric == "sl":
        if not b:
            return None
        rel = (s - b) / b
        return rel, f"SL {_pct(rel)} {'tighter' if rel < 0 else 'wider'}"
    if metric == "tp_r":
        if not b:
            return None
        rel = (s - b) / b
        return rel, f"targets {_pct(rel)} {'closer' if rel < 0 else 'further'}"
    if metric == "duration":
        if not b:
            return None
        rel = (s - b) / b
        return rel, f"held {_pct(rel)} {'shorter' if rel < 0 else 'longer'}"
    if metric == "win_rate":
        rel = (s - b) / max(b, 0.1)
        return rel, f"win rate {round(s * 100)}% vs {round(b * 100)}%"
    if metric == "avg_r":
        rel = (s - b) / max(abs(b), 0.25)
        return rel, f"average {_r(s)} vs {_r(b)}"
    return None


def insights(rows: list[Row], source: str = "backtest", limit: int = 3) -> list[dict]:
    """Top `limit` slice-vs-baseline differences, one per slice, biggest (effect × √n) first."""
    if len(rows) < MIN_SLICE + 1:
        return []
    base = _measures(rows, source)
    candidates: list[dict] = []
    for dim, key, name in DIMENSIONS:
        groups: dict[str, list[Row]] = defaultdict(list)
        for r in rows:
            k = key(r)
            if k:
                groups[k].append(r)
        for k, slice_rows in groups.items():
            n = len(slice_rows)
            if n < MIN_SLICE or n == len(rows):
                continue
            measured = _measures(slice_rows, source)
            best: tuple[float, str, str, float, float] | None = None
            for metric, s in measured.items():
                b = base.get(metric)
                if s is None or b is None:
                    continue
                described = _describe(metric, s, b)
                if not described:
                    continue
                rel, phrase = described
                if abs(rel) < MIN_EFFECT:
                    continue
                if best is None or abs(rel) > abs(best[0]):
                    best = (rel, phrase, metric, s, b)
            if not best:
                continue
            rel, phrase, metric, s, b = best
            early = n < SOLID_SLICE
            text = f"{name(k)}: {phrase}, n={n}" + (" · early signal" if early else "")
            candidates.append(
                {
                    "dimension": dim,
                    "key": k,
                    "metric": metric,
                    "text": text,
                    "n": n,
                    "early": early,
                    "slice_value": round(s, 4),
                    "baseline_value": round(b, 4),
                    "effect": round(rel, 4),
                    "score": abs(rel) * math.sqrt(n),
                }
            )
    candidates.sort(key=lambda c: (-c["score"], c["dimension"], c["key"]))
    for c in candidates:
        c["score"] = round(c["score"], 4)
    return candidates[:limit]
