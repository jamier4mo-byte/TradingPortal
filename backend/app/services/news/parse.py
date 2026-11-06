"""Figures as the feeds publish them ("0.3%", "185K", "-1.2B", "<0.1", "") ↔ numbers.

A parsed figure keeps its unit suffix and published precision so a number from JBlanked (a bare float)
can be written back in Forex Factory's style, and a surprise can be shown in the published unit.
"""

import math
import re
from dataclasses import dataclass

MINUS = "−"  # U+2212, used in everything we display
MULTIPLIERS = {"": 1.0, "%": 1.0, "K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
_FIGURE = re.compile(r"^(?P<cmp>[<>]=?)?(?P<sign>[-+−]?)(?P<num>\d+(?:\.\d+)?|\.\d+)(?P<unit>[%KMBT]?)$")


@dataclass(frozen=True)
class Figure:
    value: float  # in base units: "185K" → 185000.0, "0.3%" → 0.3
    unit: str  # "", "%", "K", "M", "B" or "T"
    decimals: int  # published precision: "0.30%" → 2


def parse_figure(text: str | None) -> Figure | None:
    """None for blank or unreadable text. "<0.1" reads as 0.1 (an upper bound is the best we have)."""
    if text is None:
        return None
    s = str(text).strip().replace(" ", "").replace(",", "").upper()
    m = _FIGURE.match(s) if s else None
    if not m:
        return None
    num, unit = m.group("num"), m.group("unit") or ""
    decimals = len(num.split(".", 1)[1]) if "." in num else 0
    value = float(num) * MULTIPLIERS[unit]
    if m.group("sign") in ("-", "−"):
        value = -value
    return Figure(value=value, unit=unit, decimals=decimals)


def parse_value(text: str | None) -> float | None:
    fig = parse_figure(text)
    return fig.value if fig else None


def natural_decimals(x: float) -> int:
    """The fewest decimals (max 4) that show a float as a person would write it."""
    for d in range(5):
        if math.isclose(round(x, d), x, abs_tol=1e-9):
            return d
    return 4


def format_figure(value: float, unit: str = "", decimals: int | None = None) -> str:
    """Base-unit value → published style, with the feeds' ASCII "-" (display code swaps in "−")."""
    scaled = value / MULTIPLIERS.get(unit, 1.0)
    if decimals is None:
        decimals = natural_decimals(scaled)
    body = f"{abs(scaled):.{decimals}f}"
    sign = "-" if scaled < 0 and float(body) != 0 else ""
    return f"{sign}{body}{unit}"


def style_like(raw: float | None, *examples: str | None) -> tuple[str | None, float | None]:
    """A JBlanked float written in the style of the Forex Factory figures for the same release.

    JBlanked figures are as published without the suffix (NFP 254.0 means "254K"), so the unit and the
    precision come from FF's forecast/previous when it has them. Returns (text, base-unit value).
    """
    if raw is None:
        return None, None
    try:
        raw = float(raw)
    except (TypeError, ValueError):
        return None, None
    if not math.isfinite(raw):
        return None, None
    style = next((f for f in (parse_figure(e) for e in examples) if f), None)
    if style is None:
        return format_figure(raw), raw
    decimals = min(max(style.decimals, natural_decimals(raw)), 4)
    value = raw * MULTIPLIERS[style.unit]
    return format_figure(value, style.unit, decimals), value


def surprise(
    actual: str | None,
    forecast: str | None,
    actual_value: float | None,
    forecast_value: float | None,
    higher_is_better: bool | None,
) -> dict | None:
    """EventOut.surprise, only when both numbers are known. `diff` is in the published unit (K, %…):
    "−15K" has diff −15. Inline when equal after rounding to the published precision."""
    if actual_value is None or forecast_value is None:
        return None
    fa, ff = parse_figure(actual), parse_figure(forecast)
    unit = fa.unit if fa else ff.unit if ff else ""
    decimals = max(fa.decimals if fa else 0, ff.decimals if ff else 0)
    diff = round((actual_value - forecast_value) / MULTIPLIERS.get(unit, 1.0), decimals)
    if diff == 0:
        return {
            "direction": "inline",
            "diff": 0.0,
            "diff_text": f"{0:.{decimals}f}{unit}",
            "better": None,
            "wording": "In line with forecast",
        }
    direction = "up" if diff > 0 else "down"
    better = None if higher_is_better is None else (direction == "up") == higher_is_better
    if better is None:
        wording = "Above forecast" if direction == "up" else "Below forecast"
    else:
        wording = "Better than forecast" if better else "Worse than forecast"
    sign = "+" if diff > 0 else MINUS
    return {
        "direction": direction,
        "diff": diff,
        "diff_text": f"{sign}{abs(diff):.{decimals}f}{unit}",
        "better": better,
        "wording": wording,
    }
