"""The Hub's engagement data (Foundations: Motion › Engaging touches; F15 first-run checklist).

Everything here is computed from existing tables; the only thing written is the user's last Hub visit,
kept in the `app_state` key → JSON store. `now` is passed in so tests can freeze the clock.

Rules of the house: streaks and bests reward process (showing up, following the rules), never profit on
its own. The one exception is "best month in R", which the Foundations doc names explicitly.
"""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AppState, JournalSession, PushSubscription, Strategy, Trade, User, UserApiKey
from . import journal as journal_svc
from .journal_rules import to_uk

STREAK_DAYS = 28  # dots on the "Showing up" card
NEW_BEST_DAYS = 7  # a best achieved within this many days is "new" (one restrained celebration)
MIN_RULE_RUN = 3  # a run of rule-following trades shorter than this isn't a "best" worth a badge
WELCOME_BACK_AFTER = timedelta(hours=24)
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _iso(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _uk_date(moment: datetime) -> date:
    return to_uk(moment).date()


def visit_key(user_id: int) -> str:
    return f"hub_visit:{user_id}"


# ---- welcome back ---------------------------------------------------------------------------


def record_visit(db: Session, user: User, now: datetime) -> bool:
    """True when the previous Hub visit was ≥ 24 h ago, or on a first visit by an account older than a day.

    The visit is recorded after the previous value is read, so the answer describes the gap just closed.
    """
    row = db.get(AppState, visit_key(user.id))
    if row is None:
        created = user.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        welcome = now - created >= WELCOME_BACK_AFTER
        db.add(AppState(key=visit_key(user.id), value={"at": _iso(now)}))
    else:
        previous = _parse(row.value.get("at") if isinstance(row.value, dict) else None)
        welcome = previous is None or now - previous >= WELCOME_BACK_AFTER
        row.value = {"at": _iso(now)}
    db.commit()
    return welcome


# ---- process streak ------------------------------------------------------------------------


def active_dates(db: Session, user: User) -> set[date]:
    """UK dates on which the user showed up: created a session, wrote a session's improve note, logged an
    ideal or backtest trade, or annotated / completed a trade."""
    dates: set[date] = set()
    sessions = db.execute(
        select(JournalSession.created_at, JournalSession.updated_at, JournalSession.improve_note).where(
            JournalSession.owner_id == user.id, JournalSession.deleted_at.is_(None)
        )
    ).all()
    for created, updated, note in sessions:
        dates.add(_uk_date(created))
        if note:
            dates.add(_uk_date(updated))
    trades = db.execute(
        select(Trade.created_at, Trade.annotated_at, Trade.kind).where(
            Trade.owner_id == user.id, Trade.deleted_at.is_(None)
        )
    ).all()
    for created, annotated, kind in trades:
        if kind in ("ideal", "backtest"):
            dates.add(_uk_date(created))
        if annotated is not None:
            dates.add(_uk_date(annotated))
    return dates


def streak(dates: set[date], today: date) -> dict:
    """Current run counted back from today (today doesn't break it until it's over), best run ever,
    and the last 28 UK dates for the dots."""
    active_today = today in dates
    cursor = today if active_today else today - timedelta(days=1)
    current = 0
    while cursor in dates:
        current += 1
        cursor -= timedelta(days=1)
    best = run = 0
    previous: date | None = None
    for d in sorted(dates):
        run = run + 1 if previous is not None and d - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = d
    first = today - timedelta(days=STREAK_DAYS - 1)
    days = [
        {"date": (first + timedelta(days=i)).isoformat(), "active": (first + timedelta(days=i)) in dates}
        for i in range(STREAK_DAYS)
    ]
    return {
        "current_days": current,
        "best_days": best,
        "active_today": active_today,
        "last_active_date": max(dates).isoformat() if dates else None,
        "days": days,
    }


# ---- personal bests ------------------------------------------------------------------------


def _booked_at(t: Trade) -> datetime:
    return t.closed_at or t.opened_at


def _rules_kept(t: Trade) -> bool | None:
    """Same reading as analytics.rows.Row.rules_kept: None when no rule is marked on the trade."""
    rules = t.rules_followed or {}
    if not rules:
        return None
    return all(bool(v) for v in rules.values())


def _month_label(d: date) -> str:
    return d.strftime("%B %Y")


def _day_label(d: date) -> str:
    return f"{d.day} {d.strftime('%b %Y')}"


def backtest_trades(db: Session, user: User) -> list[Trade]:
    return list(
        db.scalars(
            select(Trade)
            .where(Trade.owner_id == user.id, Trade.deleted_at.is_(None), Trade.kind == "backtest")
            .order_by(Trade.opened_at, Trade.id)
        ).all()
    )


def personal_bests(trades: list[Trade], now: datetime) -> list[dict]:
    bests: list[dict] = []
    fresh_after = now - timedelta(days=NEW_BEST_DAYS)

    # Best calendar month (UK) in total R. The month "happened" when its trades were logged, so a freshly
    # imported month counts as new.
    by_month: dict[tuple[int, int], list[Trade]] = defaultdict(list)
    for t in trades:
        if t.r_multiple is not None:
            by_month[(t.market_date.year, t.market_date.month)].append(t)
    if by_month:
        (year, month), month_trades = max(by_month.items(), key=lambda kv: sum(t.r_multiple for t in kv[1]))
        total = sum(t.r_multiple for t in month_trades)
        achieved = max(t.created_at for t in month_trades)
        bests.append(
            {
                "key": "best_month_r",
                "label": "Best month",
                "value": round(total, 2),
                "value_text": f"{total:+.1f} R",
                "detail": _month_label(date(year, month, 1)),
                "achieved_at": _iso(achieved),
                "is_new": achieved >= fresh_after,
            }
        )

    # Longest run of consecutive backtest trades (by booking time) with every rule followed. Trades with no
    # rules marked carry no information, so they neither extend nor break a run.
    ordered = sorted(trades, key=lambda t: (_booked_at(t), t.id))
    best_run: list[Trade] = []
    run: list[Trade] = []
    for t in ordered:
        kept = _rules_kept(t)
        if kept is None:
            continue
        if kept:
            run.append(t)
            if len(run) > len(best_run):
                best_run = list(run)
        else:
            run = []
    if len(best_run) >= MIN_RULE_RUN:
        achieved = max(t.updated_at for t in best_run)
        bests.append(
            {
                "key": "longest_rule_run",
                "label": "Longest rule run",
                "value": float(len(best_run)),
                "value_text": f"{len(best_run)} trades",
                "detail": f"to {_day_label(_uk_date(_booked_at(best_run[-1])))}",
                "achieved_at": _iso(achieved),
                "is_new": achieved >= fresh_after,
            }
        )
    return bests


# ---- first-run checklist (F15) ---------------------------------------------------------------


def checklist(db: Session, user: User) -> dict:
    def exists(stmt) -> bool:
        return (db.scalar(select(func.count()).select_from(stmt.subquery())) or 0) > 0

    out = {
        "twelve_data_key": exists(
            select(UserApiKey.id).where(
                UserApiKey.owner_id == user.id,
                UserApiKey.provider == "twelve_data",
                UserApiKey.deleted_at.is_(None),
            )
        ),
        "strategy_created": exists(
            select(Strategy.id).where(Strategy.owner_id == user.id, Strategy.deleted_at.is_(None))
        ),
        "first_csv_imported": exists(
            select(JournalSession.id).where(
                JournalSession.owner_id == user.id,
                JournalSession.deleted_at.is_(None),
                JournalSession.kind.in_(("ideal", "backtest")),
            )
        ),
        "alerts_enabled": exists(select(PushSubscription.id).where(PushSubscription.user_id == user.id)),
    }
    out["all_done_server"] = all(out.values())
    return out


# ---- week behind ---------------------------------------------------------------------------


def week_window(now: datetime) -> tuple[date, date, bool]:
    """Last Monday–Sunday (UK), and whether the recap shows: Sunday from 18:00 UK through Monday 23:59.

    On Sunday evening the week that is just ending is "last week"; on Monday it is the one that ended
    yesterday; any other day it is the most recent complete week (hidden, but still computed).
    """
    uk = to_uk(now)
    today = uk.date()
    weekday = today.weekday()  # Monday 0 … Sunday 6
    if weekday == 6:
        start = today - timedelta(days=6)
        show = uk.hour >= 18
    else:
        start = today - timedelta(days=weekday + 7)
        show = weekday == 0
    return start, start + timedelta(days=6), show


def week_recap(db: Session, user: User, now: datetime) -> dict:
    start, end, show = week_window(now)
    trades = list(
        db.scalars(
            select(Trade).where(
                Trade.owner_id == user.id,
                Trade.deleted_at.is_(None),
                Trade.kind != "missed",
                Trade.market_date >= start,
                Trade.market_date <= end,
            )
        ).all()
    )
    session_times = db.scalars(
        select(JournalSession.created_at).where(
            JournalSession.owner_id == user.id, JournalSession.deleted_at.is_(None)
        )
    ).all()
    sessions = sum(1 for created in session_times if start <= _uk_date(created) <= end)
    stats = journal_svc.headline_stats(trades, user.breakeven_threshold)
    by_day: dict[date, float] = defaultdict(float)
    for t in trades:
        if t.r_multiple is not None:
            by_day[t.market_date] += t.r_multiple
    best_day = max(by_day.items(), key=lambda kv: kv[1]) if by_day else None
    return {
        "show": show,
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "sessions": sessions,
        "trades": stats["trades"],
        "total_r": stats["total_r"],
        "total_pnl": stats["total_pnl"],
        "win_rate": stats["win_rate"],
        "rules_kept_rate": stats["rules_followed_rate"],
        "best_day": WEEKDAYS[best_day[0].weekday()] if best_day else None,
        "best_day_r": round(best_day[1], 2) if best_day else None,
    }


# ---- the whole answer ----------------------------------------------------------------------


def hub(db: Session, user: User, now: datetime) -> dict:
    today = _uk_date(now)
    return {
        "welcome_back": record_visit(db, user, now),
        "server_now": _iso(now),
        "streak": streak(active_dates(db, user), today),
        "personal_bests": personal_bests(backtest_trades(db, user), now),
        "checklist": checklist(db, user),
        "week_recap": week_recap(db, user, now),
    }
