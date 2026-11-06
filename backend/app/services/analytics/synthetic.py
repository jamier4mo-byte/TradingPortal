"""Deterministic synthetic trades for the dev seed, the performance test and the e2e analytics screens.

Never used for anything Jamie sees as real: the dev seed writes them to /tmp/tp-dev only.
"""

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import insert
from sqlalchemy.orm import Session

from ...models import Strategy, Trade
from .. import journal_rules as rules

MODELS = ("FVG", "Breaker", "OTE", "Order block")


def trade_dicts(
    strategy: Strategy,
    owner_id: int,
    n: int,
    *,
    kind: str = "backtest",
    seed: int = 7,
    start: datetime | None = None,
) -> list[dict]:
    """`n` plausible NAS100 trades, two or three a weekday, R drawn from a mildly positive edge."""
    rng = random.Random(seed)
    when = start or datetime(2025, 3, 3, 8, 0, tzinfo=UTC)
    rule_keys = [r["key"] for r in strategy.rules] or ["r1", "r2", "r3", "r4"]
    out: list[dict] = []
    for i in range(n):
        when += timedelta(hours=rng.choice((3, 5, 7, 21)))
        if when.weekday() >= 5:
            when += timedelta(days=7 - when.weekday())
        side = rng.choice(("buy", "sell"))
        model = rng.choice(MODELS)
        sl_pts = round(rng.uniform(25, 90), 1)
        tp_r = round(rng.choice((2.0, 2.5, 3.0, 4.0)), 2)
        roll = rng.random()
        if kind == "ideal":
            r = round(rng.uniform(1.5, tp_r + 1.5), 2)
        elif roll < 0.42:
            r = round(rng.uniform(1.2, tp_r), 2)
        elif roll < 0.5:
            r = 0.0
        else:
            r = -1.0 if rng.random() < 0.85 else round(rng.uniform(-1.0, -0.3), 2)
        pnl = round(r * 100, 2)
        mfe = round(max(r, 0) + rng.uniform(0.0, 2.0), 2)
        mae = round(-rng.uniform(0.0, 0.9 if r > 0 else 1.0), 2)
        broken = rng.random() < 0.25
        rules_followed = {k: not (broken and j == (i % len(rule_keys))) for j, k in enumerate(rule_keys)}
        held = timedelta(minutes=rng.randint(10, 600))
        entry = 21000 + rng.uniform(-800, 800)
        direction = 1 if side == "buy" else -1
        out.append(
            {
                "owner_id": owner_id,
                "strategy_id": strategy.id,
                "kind": kind,
                "instrument": "NAS100",
                "side": side,
                "opened_at": when,
                "closed_at": when + held,
                "market_date": rules.market_date(when),
                "session_label": rules.session_label(when),
                "duration_seconds": int(held.total_seconds()),
                "entry_price": round(entry, 1),
                "initial_sl": round(entry - direction * sl_pts, 1),
                "max_tp": round(entry + direction * sl_pts * tp_r, 1),
                "exit_price": round(entry + direction * sl_pts * r, 1),
                "sl_distance": sl_pts,
                "tp_distance": round(sl_pts * tp_r, 1),
                "tp_r": tp_r,
                "r_multiple": r,
                "pnl": pnl,
                "outcome": rules.classify_outcome(pnl),
                "entry_model": model,
                "reasoning": {"htf_bias": "Bullish" if side == "buy" else "Bearish", "pd_array": model},
                "notes": "",
                "rules_followed": rules_followed if kind == "backtest" else {},
                "mae_r": mae,
                "mfe_r": mfe,
                "created_at": when,
                "updated_at": when,
            }
        )
    return out


def insert_trades(db: Session, rows: list[dict]) -> None:
    db.execute(insert(Trade), rows)
    db.commit()
