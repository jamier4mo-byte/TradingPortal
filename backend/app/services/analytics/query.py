"""POST /api/analytics/query: load the rows in scope, apply the 2.4 filters, compute every block.

Rows are read with one column select plus one tag select (no ORM objects, no screenshots), so 5,000 trades
come back well inside the 300 ms budget.
"""

import math
from collections import Counter
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import JournalSession, Strategy, Tag, Trade, User, trade_tags
from ...schemas.analytics import AnalyticsFilters, AnalyticsQuery
from ..fxreplay import target_r
from ..journal import JournalError, get_strategy
from ..journal_rules import DEFAULT_BREAKEVEN_THRESHOLD
from ..tags import resolve_tag
from . import series
from .insights import insights
from .metrics import compute, registry_meta
from .reconcile import reconcile_session
from .rows import WEEKDAYS, Row, prepare

TRADE_LIST_LIMIT = 300
OWNER_KPIS = ("trades", "win_rate", "total_r", "avg_r", "profit_factor", "max_dd_r", "net_pnl")

_COLUMNS = (
    Trade.id,
    Trade.kind,
    Trade.opened_at,
    Trade.closed_at,
    Trade.instrument,
    Trade.side,
    Trade.owner_id,
    Trade.strategy_id,
    Trade.session_id,
    Trade.r_multiple,
    Trade.pnl,
    Trade.outcome,
    Trade.entry_model,
    Trade.session_label,
    Trade.duration_seconds,
    Trade.rules_followed,
    Trade.mae_r,
    Trade.mfe_r,
    Trade.sl_distance,
    Trade.tp_distance,
    Trade.tp_r,
    Trade.news_impact,
    Trade.market_date,
    Trade.entry_price,
    Trade.initial_sl,
    Trade.ideal_tp,
)


def _finite(v: float | None) -> float | None:
    """Belt and braces: a non-finite number stored before validation existed is treated as missing."""
    return v if v is None or math.isfinite(v) else None


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=UTC)


def load_rows(
    db: Session, user: User, *, kinds: list[str], strategy_id: int | None, scope: str = "everyone"
) -> list[Row]:
    conditions = [Trade.deleted_at.is_(None), Trade.kind.in_(kinds), Strategy.deleted_at.is_(None)]
    if strategy_id is not None:
        conditions.append(Trade.strategy_id == strategy_id)
    if scope == "mine":
        conditions.append(Trade.owner_id == user.id)
    elif scope == "others":
        conditions.append(Trade.owner_id != user.id)
    stmt = select(*_COLUMNS).join(Strategy, Strategy.id == Trade.strategy_id).where(*conditions)
    tag_stmt = (
        select(trade_tags.c.trade_id, Tag.id, Tag.name)
        .join(Tag, Tag.id == trade_tags.c.tag_id)
        .join(Trade, Trade.id == trade_tags.c.trade_id)
        .join(Strategy, Strategy.id == Trade.strategy_id)
        .where(*conditions)
    )
    tags: dict[int, list[tuple[int, str]]] = {}
    for trade_id, tag_id, name in db.execute(tag_stmt):
        tags.setdefault(trade_id, []).append((tag_id, name))
    rows: list[Row] = []
    for t in db.execute(stmt):
        mfe = t.mfe_r
        if mfe is None and t.entry_price is not None and t.initial_sl is not None and t.ideal_tp is not None:
            mfe = target_r(t.side, t.entry_price, t.initial_sl, t.ideal_tp)  # FX Replay's best price as R
        own_tags = tags.get(t.id, [])
        rows.append(
            Row(
                id=t.id,
                kind=t.kind,
                opened_at=_aware(t.opened_at),
                closed_at=_aware(t.closed_at),
                instrument=t.instrument,
                side=t.side,
                owner_id=t.owner_id,
                strategy_id=t.strategy_id,
                session_id=t.session_id,
                r=_finite(t.r_multiple),
                pnl=_finite(t.pnl),
                outcome=t.outcome,
                entry_model=t.entry_model,
                session_label=t.session_label,
                duration_seconds=t.duration_seconds,
                tags=tuple(n for _, n in own_tags),
                tag_ids=frozenset(i for i, _ in own_tags),
                rules=dict(t.rules_followed or {}),
                mae_r=_finite(t.mae_r),
                mfe_r=_finite(mfe),
                sl_distance=_finite(t.sl_distance),
                tp_distance=_finite(t.tp_distance),
                tp_r=_finite(t.tp_r),
                news_impact=t.news_impact,
                market_date=t.market_date,
            )
        )
    return rows


def _minutes(clock: str) -> int:
    hh, mm = clock.split(":")
    return int(hh) * 60 + int(mm)


def apply_filters(
    rows: list[Row], f: AnalyticsFilters, *, tag_ids: set[int] | None, news_known: bool
) -> list[Row]:
    """Every filter is AND-ed; values within one filter are OR-ed. Outcome applies to backtest trades only."""
    instruments = {i.upper() for i in f.instruments}
    sessions, models, weekdays = set(f.sessions), set(f.entry_models), set(f.weekdays)
    directions, outcomes, owners = set(f.directions), set(f.outcomes), set(f.owners)
    start = _minutes(f.time_from) if f.time_from else None
    end = _minutes(f.time_to) if f.time_to else None

    def keep(r: Row) -> bool:
        if f.date_from and r.market_date < f.date_from:  # type: ignore[operator]
            return False
        if f.date_to and r.market_date > f.date_to:  # type: ignore[operator]
            return False
        if instruments and r.instrument.upper() not in instruments:
            return False
        if sessions and r.session_label not in sessions:
            return False
        if start is not None or end is not None:
            lo = start if start is not None else 0
            hi = end if end is not None else 24 * 60
            inside = lo <= r.uk_minute < hi if lo <= hi else (r.uk_minute >= lo or r.uk_minute < hi)
            if not inside:
                return False
        if weekdays and r.weekday not in weekdays:
            return False
        if models and (r.entry_model or "") not in models:
            return False
        if directions and r.side not in directions:
            return False
        if tag_ids is not None and not (r.tag_ids & tag_ids):
            return False
        if outcomes and r.kind == "backtest" and r.outcome not in outcomes:
            return False
        if owners and r.owner_id not in owners:
            return False
        if f.rules == "all_kept" and r.rules_kept is not True:
            return False
        if f.rules == "any_broken" and r.rules_kept is not False:
            return False
        if f.news and news_known:
            if (f.news == "inside") != (r.news_impact is not None):
                return False
        return True

    return [r for r in rows if keep(r)]


def _options(rows: list[Row], users: dict[int, User]) -> dict:
    """Filter choices come from the unfiltered rows, so a choice never disappears while it's selected."""
    return {
        "instruments": sorted({r.instrument for r in rows}),
        "sessions": [s for s in series.SESSION_ORDER if any(r.session_label == s for r in rows)],
        "entry_models": sorted({r.entry_model for r in rows if r.entry_model}),
        "tags": [name for name, _ in Counter(t for r in rows for t in r.tags).most_common()],
        "owners": [_user_out(users[i]) for i in sorted({r.owner_id for r in rows}) if i in users],
        "date_min": min((r.market_date for r in rows), default=None),
        "date_max": max((r.market_date for r in rows), default=None),
    }


def _user_out(u: User) -> dict:
    return {"id": u.id, "display_name": u.display_name, "colour_index": u.colour_index, "status": u.status}


def _trade_list(rows: list[Row]) -> list[dict]:
    latest = sorted(rows, key=lambda r: (r.opened_at, r.id), reverse=True)[:TRADE_LIST_LIMIT]
    return [
        {
            "id": r.id,
            "strategy_id": r.strategy_id,
            "kind": r.kind,
            "opened_at": r.opened_at.isoformat(),
            "instrument": r.instrument,
            "side": r.side,
            "r": r.r,
            "pnl": r.pnl,
            "outcome": r.outcome,
            "entry_model": r.entry_model,
            "session_label": r.session_label,
            "owner_id": r.owner_id,
        }
        for r in latest
    ]


def _profile_summary(rows: list[Row]) -> dict:
    def top(counter: Counter, n: int) -> list[dict]:
        return [{"label": k, "count": v} for k, v in counter.most_common(n)]

    return {
        "entry_hours": top(Counter(f"{r.hour:02d}:00" for r in rows), 5),
        "sessions": top(Counter(r.session_label for r in rows if r.session_label), 4),
        "entry_models": top(Counter(r.entry_model for r in rows if r.entry_model), 5),
        "weekdays": top(Counter(WEEKDAYS[r.weekday] for r in rows), 7),
        "tags": top(Counter(t for r in rows for t in r.tags), 8),
        "instruments": top(Counter(r.instrument for r in rows), 4),
        "sides": top(Counter("Long" if r.side == "buy" else "Short" for r in rows), 2),
    }


def backtest_block(rows: list[Row], rules: list[dict] | None) -> dict:
    return {
        "kpis": compute(rows, "backtest"),
        "equity": series.equity(rows),
        "streaks": series.streak_runs(rows),
        "breakdowns": series.breakdowns(rows),
        "calendar": series.calendar(rows),
        "r_distribution": series.r_distribution(rows),
        "heatmap": series.heatmap(rows),
        "rulebook": series.rulebook(rows, rules),
        "excursions": series.excursions(rows),
        "r_sequence": [round(r.r, 4) for r in rows if r.r is not None],
    }


def ideal_block(rows: list[Row]) -> dict:
    b = series.breakdowns(rows)
    return {
        "kpis": compute(rows, "ideal"),
        "distributions": series.ideal_distributions(rows),
        "heatmap": series.heatmap(rows),
        "breakdowns": {
            k: b[k] for k in ("entry_model", "weekday", "session", "hour", "direction", "instrument")
        },
        "profile": _profile_summary(rows),
    }


def owner_split(rows: list[Row], users: dict[int, User]) -> list[dict]:
    out = []
    for owner_id, owned in sorted(series.by_owner(rows).items()):
        kpis = compute(owned, "backtest")
        cum, curve = 0.0, []
        for r in owned:
            cum += r.r or 0.0
            curve.append(round(cum, 4))
        out.append(
            {
                "owner": _user_out(users[owner_id]) if owner_id in users else {"id": owner_id},
                "kpis": {k: kpis.get(k) for k in OWNER_KPIS},
                "equity": curve,
            }
        )
    return out


def reconcile(db: Session, strategy: Strategy, kinds: list[str]) -> list[dict]:
    sessions = db.scalars(
        select(JournalSession)
        .where(
            JournalSession.strategy_id == strategy.id,
            JournalSession.deleted_at.is_(None),
            JournalSession.kind.in_([k for k in kinds if k in ("ideal", "backtest")]),
        )
        .order_by(JournalSession.created_at.asc())
    )
    out = []
    for s in sessions:
        if not s.import_report:
            continue  # manual logging runs have nothing to reconcile against
        trades = list(db.scalars(select(Trade).where(Trade.session_id == s.id)))
        out.append(reconcile_session(s, trades))
    return out


def run_query(db: Session, user: User, q: AnalyticsQuery) -> dict:
    strategy = None
    if q.strategy_id is not None:
        strategy = get_strategy(db, q.strategy_id)
    kinds = {"ideal": ["ideal"], "backtest": ["backtest"], "compare": ["ideal", "backtest"]}[q.source]
    threshold = (
        user.breakeven_threshold if user.breakeven_threshold is not None else DEFAULT_BREAKEVEN_THRESHOLD
    )
    rows = prepare(load_rows(db, user, kinds=kinds, strategy_id=q.strategy_id, scope=q.scope), threshold)
    owner_ids = {r.owner_id for r in rows} | set(q.filters.owners)
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(owner_ids)))} if owner_ids else {}

    tag_ids: set[int] | None = None
    unresolved: list[str] = []
    if q.filters.tags:
        tag_ids = set()
        for name in q.filters.tags:
            tag = resolve_tag(db, name)
            if tag:
                tag_ids.add(tag.id)
            else:
                unresolved.append(name)
    news_known = any(r.news_impact is not None for r in rows)
    filtered = apply_filters(rows, q.filters, tag_ids=tag_ids, news_known=news_known)
    ideal = [r for r in filtered if r.kind == "ideal"]
    backtest = [r for r in filtered if r.kind == "backtest"]
    primary = backtest if q.source in ("backtest", "compare") else ideal
    if q.source == "compare" and not backtest:
        primary = ideal

    if strategy and strategy.rules:
        rules = strategy.rules
    else:
        rules = None
    return {
        "source": q.source,
        "strategy_id": q.strategy_id,
        "scope": q.scope,
        "split_by_owner": q.split_by_owner,
        "filters": q.filters.model_dump(mode="json"),
        "breakeven_threshold": threshold,
        "counts": {
            "in_scope": len(rows),
            "filtered": len(filtered),
            "ideal": len(ideal),
            "backtest": len(backtest),
        },
        "news_status": "ok" if news_known else "no_data",
        "notes": {
            "unresolved_tags": unresolved,
            "news": None if news_known else "No news data",
        },
        "registry": registry_meta(q.source),
        "options": _options(rows, users),
        "backtest": backtest_block(backtest, rules) if q.source in ("backtest", "compare") else None,
        "ideal": ideal_block(ideal) if q.source in ("ideal", "compare") else None,
        "compare": series.compare(ideal, backtest) if q.source == "compare" else None,
        "owners": owner_split(primary, users) if q.split_by_owner else None,
        "insights": insights(primary, "backtest" if primary is backtest else "ideal"),
        "reconcile": reconcile(db, strategy, kinds) if strategy else [],
        "trades": _trade_list(primary),
    }


__all__ = ["JournalError", "apply_filters", "load_rows", "run_query"]
