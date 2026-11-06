"""Replay Journal services: strategies, sessions, trades, imports, undo, trash, profile, summary."""

import hashlib
import statistics
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.deps import require_owner_or_admin
from ..core.security import utcnow
from ..models import (
    DEFAULT_REASONING_TEMPLATE,
    DEFAULT_RULES,
    LABELLED_SLOTS,
    JournalSession,
    Screenshot,
    Strategy,
    Tag,
    Trade,
    User,
)
from . import audit
from . import fxreplay as fx
from . import instruments as inst_svc
from . import journal_rules as rules
from .analytics.metrics import compute
from .analytics.reconcile import csv_totals
from .analytics.rows import Row, prepare
from .news import tagging as news_tagging
from .tags import resolve_tag

TRASH_DAYS = 30
SLOT_ORDER = {"htf": 0, "entry": 1, "outcome": 2, "extra": 3}


class JournalError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


# ---- strategies ----------------------------------------------------------------------------


def live_strategies(db: Session) -> list[Strategy]:
    return list(
        db.scalars(select(Strategy).where(Strategy.deleted_at.is_(None)).order_by(Strategy.updated_at.desc()))
    )


def get_strategy(db: Session, strategy_id: int, *, include_deleted: bool = False) -> Strategy:
    strategy = db.get(Strategy, strategy_id)
    if not strategy or (strategy.deleted_at and not include_deleted):
        raise JournalError("No such strategy.", 404)
    return strategy


def _check_rules(rules_in: list[dict]) -> list[dict]:
    cleaned = [
        {"key": r.get("key") or f"r{i + 1}", "text": (r.get("text") or "").strip()}
        for i, r in enumerate(rules_in)
    ]
    cleaned = [r for r in cleaned if r["text"]]
    if cleaned and not 4 <= len(cleaned) <= 8:
        raise JournalError("A rulebook has between 4 and 8 rules.")
    return cleaned


def create_strategy(db: Session, actor: User, **fields) -> Strategy:
    name = (fields.get("name") or "").strip()
    if not name:
        raise JournalError("Give the strategy a name.")
    fx.resolve_zone(fields.get("csv_timezone") or "Europe/London")
    strategy = Strategy(
        owner_id=actor.id,
        name=name,
        description=(fields.get("description") or "").strip(),
        instruments=[inst_svc.pair_symbol(i) for i in fields.get("instruments") or [] if i.strip()],
        timeframes=[t.strip() for t in fields.get("timeframes") or [] if t.strip()],
        entry_models=[m.strip() for m in fields.get("entry_models") or [] if m.strip()],
        csv_timezone=fields.get("csv_timezone") or "Europe/London",
        rules=_check_rules(fields.get("rules") or DEFAULT_RULES),
        reasoning_template=fields.get("reasoning_template") or DEFAULT_REASONING_TEMPLATE,
    )
    db.add(strategy)
    db.flush()
    audit.record(db, "strategy.created", actor=actor, target_type="strategy", target_id=strategy.id)
    db.commit()
    return strategy


def update_strategy(db: Session, actor: User, strategy: Strategy, **fields) -> Strategy:
    require_owner_or_admin(strategy, actor)
    for key, value in fields.items():
        if value is None:
            continue
        if key == "name":
            value = value.strip()
            if not value:
                raise JournalError("Give the strategy a name.")
        elif key == "csv_timezone":
            fx.resolve_zone(value)
        elif key == "rules":
            value = _check_rules(value)
        elif key == "instruments":
            value = [inst_svc.pair_symbol(i) for i in value if i.strip()]
        elif key in ("timeframes", "entry_models"):
            value = [v.strip() for v in value if v.strip()]
        setattr(strategy, key, value)
    strategy.profile_fingerprint = None
    audit.record(db, "strategy.updated", actor=actor, target_type="strategy", target_id=strategy.id)
    db.commit()
    return strategy


def delete_strategy(db: Session, actor: User, strategy: Strategy) -> None:
    require_owner_or_admin(strategy, actor)
    strategy.deleted_at = utcnow()
    audit.record(db, "strategy.deleted", actor=actor, target_type="strategy", target_id=strategy.id)
    db.commit()


def restore_strategy(db: Session, actor: User, strategy: Strategy) -> None:
    require_owner_or_admin(strategy, actor)
    strategy.deleted_at = None
    audit.record(db, "strategy.restored", actor=actor, target_type="strategy", target_id=strategy.id)
    db.commit()


# ---- trades -------------------------------------------------------------------------------


def live_trades(db: Session, strategy: Strategy, kind: str | None = None) -> list[Trade]:
    stmt = select(Trade).where(Trade.strategy_id == strategy.id, Trade.deleted_at.is_(None))
    if kind:
        stmt = stmt.where(Trade.kind == kind)
    return list(db.scalars(stmt.order_by(Trade.opened_at.asc(), Trade.id.asc())))


def get_trade(db: Session, trade_id: int, *, include_deleted: bool = False) -> Trade:
    trade = db.get(Trade, trade_id)
    if not trade or (trade.deleted_at and not include_deleted):
        raise JournalError("No such trade.", 404)
    return trade


def strategy_coverage(db: Session, strategy: Strategy) -> rules.Coverage:
    return rules.coverage(t.opened_at for t in live_trades(db, strategy, "ideal"))


def _distances(
    db: Session, pair: str, side: str, entry: float | None, sl: float | None, tp: float | None
) -> dict:
    out: dict = {"sl_distance": None, "tp_distance": None, "tp_r": None}
    if entry is None or sl is None:
        return out
    pip, _unit = inst_svc.pip_size_for(db, pair)
    out["sl_distance"] = round(abs(entry - sl) / pip, 2)
    if tp is not None:
        out["tp_distance"] = round(abs(tp - entry) / pip, 2)
        out["tp_r"] = fx.target_r(side, entry, sl, tp)
    return out


def _apply_tags(db: Session, trade: Trade, names: Iterable[str]) -> list[str]:
    """Resolve each name through the vocabulary; unknown names are kept in notes? No: reported back."""
    unresolved: list[str] = []
    tags: list[Tag] = []
    for name in names:
        tag = resolve_tag(db, name)
        if tag and tag not in tags:
            tags.append(tag)
        elif not tag:
            unresolved.append(name)
    trade.tags = tags
    return unresolved


def _derive(trade: Trade, threshold: float) -> None:
    trade.market_date = rules.market_date(trade.opened_at)
    trade.session_label = rules.session_label(trade.opened_at)
    trade.duration_seconds = (
        int((trade.closed_at - trade.opened_at).total_seconds()) if trade.closed_at else None
    )
    if trade.kind == "missed":
        trade.outcome = None
        trade.pnl = None
    else:
        trade.outcome = rules.classify_outcome(trade.pnl, threshold)


def create_trade(
    db: Session, actor: User, strategy: Strategy, *, tags: list[str] | None = None, **fields
) -> Trade:
    """Manual entry: quick log (ideal), backtest manual entry, or a missed setup."""
    require_owner_or_admin(strategy, actor)
    kind = fields.pop("kind", "ideal")
    if kind not in ("ideal", "backtest", "missed"):
        raise JournalError("kind must be ideal, backtest or missed.")
    opened_at = fields.pop("opened_at")
    pair = inst_svc.canonical_symbol(db, fields.pop("instrument"))
    side = fields.pop("side")
    if side not in ("buy", "sell"):
        raise JournalError("side must be buy or sell.")
    entry, sl, tp = (
        fields.pop("entry_price", None),
        fields.pop("initial_sl", None),
        fields.pop("max_tp", None),
    )
    exit_price = fields.pop("exit_price", None)
    r_multiple = fields.pop("r_multiple", None)
    if r_multiple is None and entry is not None and sl is not None:
        r_multiple = fx.realised_r(side, entry, sl, exit_price)
    session_id = fields.pop("session_id", None)
    if session_id is not None:
        session = db.get(JournalSession, session_id)
        if not session or session.deleted_at or session.strategy_id != strategy.id:
            raise JournalError("That session doesn't belong to this strategy.", 404)
        require_owner_or_admin(session, actor)
    trade = Trade(
        owner_id=strategy.owner_id if actor.is_admin and strategy.owner_id != actor.id else actor.id,
        strategy_id=strategy.id,
        session_id=session_id,
        kind=kind,
        instrument=pair,
        side=side,
        opened_at=opened_at,
        closed_at=fields.pop("closed_at", None),
        market_date=rules.market_date(opened_at),
        entry_price=entry,
        initial_sl=sl,
        max_tp=tp,
        ideal_tp=fields.pop("ideal_tp", None),
        exit_price=exit_price,
        r_multiple=r_multiple,
        pnl=fields.pop("pnl", None),
        entry_model=fields.pop("entry_model", None),
        reasoning=fields.pop("reasoning", None) or {},
        notes=fields.pop("notes", None) or "",
        rules_followed=fields.pop("rules_followed", None) or {},
        mae_r=fields.pop("mae_r", None),
        mfe_r=fields.pop("mfe_r", None),
        **_distances(db, pair, side, entry, sl, tp),
    )
    _derive(trade, actor.breakeven_threshold)
    db.add(trade)
    db.flush()
    if tags:
        _apply_tags(db, trade, tags)
    strategy.profile_fingerprint = None
    strategy.updated_at = utcnow()
    news_tagging.tag_trades(db, [trade])
    audit.record(db, "trade.created", actor=actor, target_type="trade", target_id=trade.id)
    db.commit()
    return trade


ANNOTATION_FIELDS = (
    "reasoning",
    "notes",
    "rules_followed",
    "entry_model",
    "mae_r",
    "mfe_r",
    "entry_price",
    "initial_sl",
    "max_tp",
    "exit_price",
    "pnl",
    "r_multiple",
    "opened_at",
    "closed_at",
    "side",
    "instrument",
)


def update_trade(
    db: Session,
    actor: User,
    trade: Trade,
    *,
    tags: list[str] | None = None,
    annotated: bool | None = None,
    **fields,
) -> Trade:
    require_owner_or_admin(trade, actor)
    if annotated is not None:
        trade.annotated_at = utcnow() if annotated else None
    for key, value in fields.items():
        if key not in ANNOTATION_FIELDS or value is None:
            continue
        if key == "instrument":
            value = inst_svc.canonical_symbol(db, value)
        setattr(trade, key, value)
    if any(
        k in fields and fields[k] is not None
        for k in ("entry_price", "initial_sl", "max_tp", "side", "instrument")
    ):
        for k, v in _distances(
            db, trade.instrument, trade.side, trade.entry_price, trade.initial_sl, trade.max_tp
        ).items():
            setattr(trade, k, v)
    if "exit_price" in fields and fields["exit_price"] is not None and trade.entry_price and trade.initial_sl:
        trade.r_multiple = fx.realised_r(trade.side, trade.entry_price, trade.initial_sl, trade.exit_price)
    _derive(trade, actor.breakeven_threshold)
    if tags is not None:
        _apply_tags(db, trade, tags)
    if fields.get("opened_at") is not None or fields.get("instrument") is not None:
        news_tagging.tag_trades(db, [trade])
    trade.strategy.profile_fingerprint = None
    db.commit()
    return trade


def delete_trade(db: Session, actor: User, trade: Trade) -> None:
    require_owner_or_admin(trade, actor)
    trade.deleted_at = utcnow()
    trade.strategy.profile_fingerprint = None
    audit.record(db, "trade.deleted", actor=actor, target_type="trade", target_id=trade.id)
    db.commit()


def restore_trade(db: Session, actor: User, trade: Trade) -> None:
    require_owner_or_admin(trade, actor)
    trade.deleted_at = None
    trade.strategy.profile_fingerprint = None
    db.commit()


# ---- imports (F3) --------------------------------------------------------------------------


def _existing_fx_ids(db: Session, strategy: Strategy, kind: str | None = None) -> dict[str, set[str]]:
    """Duplicate key is (strategy, destination kind, FX Replay id): a winner can sit in both catalogues."""
    stmt = select(Trade).where(
        Trade.strategy_id == strategy.id, Trade.deleted_at.is_(None), Trade.fx_id.is_not(None)
    )
    if kind:
        stmt = stmt.where(Trade.kind == kind)
    out: dict[str, set[str]] = {"ideal": set(), "backtest": set()}
    for t in db.scalars(stmt):
        out.setdefault(t.kind, set()).add(t.fx_id)
    return out


def preview_import(
    db: Session,
    actor: User,
    strategy: Strategy,
    data: bytes,
    *,
    timezone: str | None = None,
    filename: str = "",
) -> dict:
    """Parse the file and say exactly what each destination would import. Writes nothing."""
    zone = timezone or strategy.csv_timezone
    result = fx.parse_csv(data, timezone=zone)
    threshold = actor.breakeven_threshold
    existing = _existing_fx_ids(db, strategy)
    rows_out, winners = [], 0
    losers = breakevens = 0
    duplicates = {"ideal": 0, "backtest": 0}
    dates: list[date] = []
    for row in result.rows:
        outcome = rules.classify_outcome(row.pnl, threshold)
        dup_in = {k: row.fx_id in existing[k] for k in ("ideal", "backtest")}
        for k, v in dup_in.items():
            duplicates[k] += int(v)
        if outcome == "win":
            winners += 1
        elif outcome == "loss":
            losers += 1
        else:
            breakevens += 1
        dates.append(rules.market_date(row.opened_at))
        rows_out.append(
            {
                "fx_id": row.fx_id,
                "line": row.line,
                "instrument": inst_svc.canonical_symbol(db, row.pair),
                "side": row.side,
                "opened_at": row.opened_at,
                "closed_at": row.closed_at,
                "opened_uk": rules.to_uk(row.opened_at).strftime("%d %b %Y %H:%M"),
                "pnl": row.pnl,
                "r_multiple": fx.realised_r(row.side, row.entry_price, row.initial_sl, row.exit_price),
                "outcome": outcome,
                "duplicate": dup_in,
                "tags": row.tags,
            }
        )
    return {
        "filename": filename,
        "file_hash": hashlib.sha256(data).hexdigest(),
        "timezone": zone,
        "rows_parsed": len(result.rows),
        "rows_total": result.total_rows,
        "problems": result.problems,
        "unknown_columns": result.unknown_columns,
        "range_start": min(dates) if dates else None,
        "range_end": max(dates) if dates else None,
        "winners": winners,
        "losers": losers,
        "breakevens": breakevens,
        "duplicates": duplicates,
        "would_import": {
            "ideal": sum(1 for r in rows_out if r["outcome"] == "win" and not r["duplicate"]["ideal"]),
            "backtest": sum(1 for r in rows_out if not r["duplicate"]["backtest"]),
        },
        "breakeven_threshold": threshold,
        "rows": rows_out,
    }


def confirm_import(
    db: Session,
    actor: User,
    strategy: Strategy,
    data: bytes,
    *,
    destination: str,
    timezone: str | None = None,
    filename: str = "",
) -> tuple[JournalSession, dict]:
    """Create a Session and its trades. Ideal keeps winners only; Backtest keeps every row."""
    require_owner_or_admin(strategy, actor)
    if destination not in ("ideal", "backtest"):
        raise JournalError("destination must be ideal or backtest.")
    zone = timezone or strategy.csv_timezone
    result = fx.parse_csv(data, timezone=zone)
    threshold = actor.breakeven_threshold
    existing = _existing_fx_ids(db, strategy, destination)[destination]
    owner_id = strategy.owner_id if actor.is_admin and strategy.owner_id != actor.id else actor.id
    session = JournalSession(
        owner_id=owner_id,
        strategy_id=strategy.id,
        kind=destination,
        csv_timezone=zone,
        source_filename=filename or None,
        file_hash=hashlib.sha256(data).hexdigest(),
    )
    db.add(session)
    db.flush()
    imported: list[Trade] = []
    skipped_duplicates: list[str] = []
    skipped_losers = 0
    unresolved_tags: set[str] = set()
    for row in result.rows:
        if row.fx_id in existing:
            skipped_duplicates.append(row.fx_id)
            continue
        outcome = rules.classify_outcome(row.pnl, threshold)
        if destination == "ideal" and outcome != "win":
            skipped_losers += 1
            continue
        pair = inst_svc.canonical_symbol(db, row.pair)
        trade = Trade(
            owner_id=owner_id,
            strategy_id=strategy.id,
            session_id=session.id,
            kind=destination,
            fx_id=row.fx_id,
            instrument=pair,
            side=row.side,
            opened_at=row.opened_at,
            closed_at=row.closed_at,
            market_date=rules.market_date(row.opened_at),
            entry_price=row.entry_price,
            initial_sl=row.initial_sl,
            max_tp=row.max_tp,
            ideal_tp=row.ideal_tp,
            exit_price=row.exit_price,
            r_multiple=fx.realised_r(row.side, row.entry_price, row.initial_sl, row.exit_price),
            pnl=row.pnl,
            raw_row=row.raw,
            **_distances(db, pair, row.side, row.entry_price, row.initial_sl, row.max_tp),
        )
        if trade.r_multiple is None and row.avg_rr is not None:
            trade.r_multiple = row.avg_rr
        _derive(trade, threshold)
        db.add(trade)
        db.flush()
        if row.tags:
            unresolved_tags.update(_apply_tags(db, trade, row.tags))
        imported.append(trade)
        existing.add(row.fx_id)
    dates = [t.market_date for t in imported]
    session.trade_count = len(imported)
    session.range_start = min(dates) if dates else None
    session.range_end = max(dates) if dates else None
    report = {
        "imported": len(imported),
        "rows_parsed": len(result.rows),
        "duplicates": skipped_duplicates,
        "skipped_not_winners": skipped_losers,
        "problems": result.problems,
        "unresolved_tags": sorted(unresolved_tags),
        "timezone": zone,
        # Reconcile line (F16): FX Replay's own figures for the file, and what this import kept of them.
        "csv_totals": csv_totals(result.rows) if result.rows else None,
        "kept_totals": {"trades": len(imported), "rpnl_sum": round(sum(t.pnl or 0.0 for t in imported), 2)},
    }
    session.import_report = report
    news_tagging.tag_trades(db, imported)
    strategy.profile_fingerprint = None
    strategy.updated_at = utcnow()
    audit.record(
        db,
        "session.imported",
        actor=actor,
        target_type="journal_session",
        target_id=session.id,
        meta={"strategy": strategy.id, "imported": len(imported), "destination": destination},
    )
    db.commit()
    return session, report


def get_session(db: Session, session_id: int, *, include_deleted: bool = False) -> JournalSession:
    session = db.get(JournalSession, session_id)
    if not session or (session.deleted_at and not include_deleted):
        raise JournalError("No such session.", 404)
    return session


def session_trades(db: Session, session: JournalSession, *, include_deleted: bool = False) -> list[Trade]:
    stmt = select(Trade).where(Trade.session_id == session.id, Trade.strategy_id == session.strategy_id)
    if not include_deleted:
        stmt = stmt.where(Trade.deleted_at.is_(None))
    return list(db.scalars(stmt.order_by(Trade.opened_at.asc(), Trade.id.asc())))


def undo_session(db: Session, actor: User, session: JournalSession) -> int:
    """Soft-delete the session and every trade it created. Returns how many trades went."""
    require_owner_or_admin(session, actor)
    now = utcnow()
    n = 0
    for trade in session_trades(db, session):
        trade.deleted_at = now
        n += 1
    session.deleted_at = now
    session.undone_at = now
    session.strategy.profile_fingerprint = None
    audit.record(db, "session.undone", actor=actor, target_type="journal_session", target_id=session.id)
    db.commit()
    return n


def restore_session(db: Session, actor: User, session: JournalSession) -> int:
    require_owner_or_admin(session, actor)
    n = 0
    undone = session.undone_at or session.deleted_at
    for trade in session_trades(db, session, include_deleted=True):
        # Only bring back trades that went with the undo, not ones deleted on their own before it.
        if trade.deleted_at and (undone is None or abs((trade.deleted_at - undone).total_seconds()) < 2):
            trade.deleted_at = None
            n += 1
    session.deleted_at = None
    session.undone_at = None
    session.strategy.profile_fingerprint = None
    audit.record(db, "session.restored", actor=actor, target_type="journal_session", target_id=session.id)
    db.commit()
    return n


def update_session(
    db: Session, actor: User, session: JournalSession, *, improve_note: str | None = None
) -> JournalSession:
    require_owner_or_admin(session, actor)
    if improve_note is not None:
        session.improve_note = improve_note.strip()
    db.commit()
    return session


def live_sessions(db: Session, strategy: Strategy) -> list[JournalSession]:
    return list(
        db.scalars(
            select(JournalSession)
            .where(JournalSession.strategy_id == strategy.id, JournalSession.deleted_at.is_(None))
            .order_by(JournalSession.created_at.desc())
        )
    )


def session_progress(db: Session, session: JournalSession) -> dict:
    """'10 trades · 14/30 screenshots · 6/10 reasons · 4/10 completed' for the inbox (U1)."""
    trades = session_trades(db, session)
    shots = 0
    reasons = 0
    completed = 0
    for t in trades:
        slots = {s.slot for s in t.screenshots if s.deleted_at is None and s.slot in LABELLED_SLOTS}
        shots += len(slots)
        if any(str(v).strip() for v in (t.reasoning or {}).values()) or t.notes.strip():
            reasons += 1
        if t.annotated_at:
            completed += 1
    return {
        "trades": len(trades),
        "screenshots": shots,
        "screenshots_target": len(trades) * len(LABELLED_SLOTS),
        "reasons": reasons,
        "reasons_target": len(trades),
        "completed": completed,
    }


# ---- trash (F5) ----------------------------------------------------------------------------


def trash(db: Session, actor: User) -> dict:
    cutoff = utcnow() - timedelta(days=TRASH_DAYS)

    def visible(items):
        return [
            i
            for i in items
            if i.deleted_at and i.deleted_at >= cutoff and (actor.is_admin or i.owner_id == actor.id)
        ]

    strategies = visible(db.scalars(select(Strategy).where(Strategy.deleted_at.is_not(None))))
    sessions = visible(db.scalars(select(JournalSession).where(JournalSession.deleted_at.is_not(None))))
    session_ids = {s.id for s in sessions}
    trades = [
        t
        for t in visible(db.scalars(select(Trade).where(Trade.deleted_at.is_not(None))))
        if t.session_id not in session_ids or t.deleted_at != db.get(JournalSession, t.session_id).deleted_at
    ]
    return {"strategies": strategies, "sessions": sessions, "trades": trades, "days": TRASH_DAYS}


# ---- stats, profile, summary ---------------------------------------------------------------


def headline_stats(trades: list[Trade], threshold: float = rules.DEFAULT_BREAKEVEN_THRESHOLD) -> dict:
    """Strategy card and session numbers, from the same metric engine as the Analytics tab."""
    scored = [t for t in trades if t.kind != "missed"]
    rows = prepare(
        [
            Row(id=t.id, kind=t.kind, opened_at=t.opened_at, closed_at=t.closed_at, r=t.r_multiple, pnl=t.pnl,
                outcome=t.outcome, rules=dict(t.rules_followed or {}), market_date=t.market_date)
            for t in scored
        ],
        threshold,
    )  # fmt: skip
    k = compute(rows)
    return {
        "trades": len(scored),
        "win_rate": k["win_rate"],
        "total_r": round(k["total_r"], 2) if k["total_r"] is not None else None,
        "avg_r": round(k["avg_r"], 2) if k["avg_r"] is not None else None,
        "total_pnl": round(k["net_pnl"], 2) if k["net_pnl"] is not None else None,
        "rules_followed_rate": k["rules_kept_rate"],
        "profit_factor": k["profit_factor"],
        "max_dd_r": k["max_dd_r"],
    }


def r_sparkline(trades: list[Trade]) -> list[float]:
    total = 0.0
    out: list[float] = []
    for t in sorted(
        (t for t in trades if t.r_multiple is not None and t.kind != "missed"), key=lambda t: t.opened_at
    ):
        total += t.r_multiple
        out.append(round(total, 2))
    return out[-40:]


def _fingerprint(trades: list[Trade]) -> str:
    stamp = max((t.updated_at for t in trades), default=None)
    return f"{len(trades)}:{stamp.isoformat() if stamp else ''}"


def strategy_profile(db: Session, strategy: Strategy) -> dict | None:
    """Computed from the ideal trades once the strategy unlocks; cached until the trades change (2.2)."""
    ideal = live_trades(db, strategy, "ideal")
    cov = rules.coverage(t.opened_at for t in ideal)
    if not (cov.unlocked or strategy.backtest_opened_early) or not ideal:
        return None
    fp = _fingerprint(ideal)
    if strategy.profile_cache and strategy.profile_fingerprint == fp:
        return strategy.profile_cache
    profile = compute_profile(ideal)
    strategy.profile_cache = profile
    strategy.profile_fingerprint = fp
    db.commit()
    return profile


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 2) if values else None


def _top(counter: Counter, n: int = 5) -> list[dict]:
    return [{"label": k, "count": v} for k, v in counter.most_common(n)]


def compute_profile(trades: list[Trade]) -> dict:
    durations = [t.duration_seconds for t in trades if t.duration_seconds]
    hours = Counter(rules.to_uk(t.opened_at).strftime("%H:00") for t in trades)
    weekdays = Counter(rules.to_uk(t.opened_at).strftime("%a") for t in trades)
    tags = Counter(tag.name for t in trades for tag in t.tags)
    confluences = Counter()
    for t in trades:
        text = (t.reasoning or {}).get("confluences") or ""
        for part in fx.split_tags(text):
            confluences[part] += 1
    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return {
        "trades": len(trades),
        "avg_tp_distance": _mean([t.tp_distance for t in trades if t.tp_distance is not None]),
        "avg_sl_distance": _mean([t.sl_distance for t in trades if t.sl_distance is not None]),
        "avg_tp_r": _mean([t.tp_r for t in trades if t.tp_r is not None]),
        "avg_r": _mean([t.r_multiple for t in trades if t.r_multiple is not None]),
        "typical_duration_seconds": int(statistics.median(durations)) if durations else None,
        "entry_hours": _top(hours, 6),
        "sessions": _top(Counter(t.session_label for t in trades), 4),
        "entry_models": _top(Counter(t.entry_model for t in trades if t.entry_model), 6),
        "weekdays": [
            {"label": d, "count": weekdays.get(d, 0)}
            for d in order
            if weekdays.get(d, 0) or d not in ("Sat", "Sun")
        ],
        "tags": _top(tags, 8),
        "confluences": _top(confluences, 8),
        "instruments": _top(Counter(t.instrument for t in trades), 4),
        "sides": _top(Counter(t.side for t in trades), 2),
    }


def strategy_card(
    db: Session, strategy: Strategy, threshold: float = rules.DEFAULT_BREAKEVEN_THRESHOLD
) -> dict:
    trades = live_trades(db, strategy)
    ideal = [t for t in trades if t.kind == "ideal"]
    backtest = [t for t in trades if t.kind == "backtest"]
    cov = rules.coverage(t.opened_at for t in ideal)
    dates = [t.market_date for t in ideal]
    return {
        "ideal_count": len(ideal),
        "backtest_count": len(backtest),
        "missed_count": sum(1 for t in trades if t.kind == "missed"),
        "range_start": min(dates) if dates else None,
        "range_end": max(dates) if dates else None,
        "coverage": cov,
        "stage": rules.stage(cov, len(backtest)),
        "backtest_stats": headline_stats(backtest, threshold) if backtest else None,
        "sparkline": r_sparkline(backtest or ideal),
        "last_trade_at": max((t.created_at for t in trades), default=None),
    }


def summary(db: Session, actor: User) -> dict:
    """For the Hub's Replay Journal island: counts and the last session."""
    strategies = live_strategies(db)
    trade_count = db.scalar(select(func.count(Trade.id)).where(Trade.deleted_at.is_(None))) or 0
    last = db.scalar(
        select(JournalSession)
        .where(JournalSession.deleted_at.is_(None))
        .order_by(JournalSession.created_at.desc())
    )
    mine = db.scalar(
        select(JournalSession)
        .where(JournalSession.deleted_at.is_(None), JournalSession.owner_id == actor.id)
        .order_by(JournalSession.created_at.desc())
    )
    return {
        "strategies": len(strategies),
        "trades": trade_count,
        "unlocked": sum(1 for s in strategies if strategy_coverage(db, s).unlocked),
        "last_session": last,
        "my_last_session": mine,
    }


def screenshot_counts(trades: list[Trade]) -> dict[int, dict]:
    out = {}
    for t in trades:
        live = [s for s in t.screenshots if s.deleted_at is None]
        out[t.id] = {
            "htf": any(s.slot == "htf" for s in live),
            "entry": any(s.slot == "entry" for s in live),
            "outcome": any(s.slot == "outcome" for s in live),
            "extras": sum(1 for s in live if s.slot == "extra"),
        }
    return out


def live_screenshots(trade: Trade) -> list[Screenshot]:
    return sorted(
        (s for s in trade.screenshots if s.deleted_at is None),
        key=lambda s: (SLOT_ORDER.get(s.slot, 9), s.position, s.id),
    )


def session_dates_uk(opened: datetime) -> str:
    return rules.to_uk(opened).strftime("%d %b %Y")
