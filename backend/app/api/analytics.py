"""Analytics API (2.4, F16): one query endpoint for the Ideal, Backtest and Compare views."""

from fastapi import APIRouter, HTTPException

from ..core.deps import CurrentUser, Db
from ..schemas.analytics import AnalyticsQuery
from ..services import journal as journal_svc
from ..services.analytics.insights import session_insights
from ..services.analytics.metrics import registry_meta
from ..services.analytics.query import load_rows, run_query
from ..services.analytics.rows import prepare
from ..services.journal import JournalError

router = APIRouter(tags=["analytics"])


@router.post("/analytics/query")
def analytics_query(body: AnalyticsQuery, user: CurrentUser, db: Db) -> dict:
    """KPIs, series and the metric registry for the current filters. Everyone can read everyone's trades."""
    try:
        return run_query(db, user, body)
    except JournalError as exc:
        raise HTTPException(exc.status, exc.message) from exc


@router.get("/analytics/registry")
def analytics_registry(_: CurrentUser) -> list[dict]:
    """Every metric's id, label, unit and formula text (the tooltips)."""
    return registry_meta()


@router.get("/journal/sessions/{session_id}/insights")
def get_session_insights(session_id: int, user: CurrentUser, db: Db) -> dict:
    """Auto-insights for the session recap card (U11): plain Python, computed on request."""
    try:
        session = journal_svc.get_session(db, session_id)
    except JournalError as exc:
        raise HTTPException(exc.status, exc.message) from exc
    kinds = [session.kind] if session.kind in ("ideal", "backtest") else ["ideal", "backtest"]
    rows = prepare(
        load_rows(db, user, kinds=kinds, strategy_id=session.strategy_id), user.breakeven_threshold
    )
    in_session = [r for r in rows if r.session_id == session.id]
    source = (
        "backtest" if any(r.kind == "backtest" for r in in_session) or session.kind == "backtest" else "ideal"
    )
    pool = [r for r in rows if r.kind == source]
    return session_insights([r for r in in_session if r.kind == source], pool, source)
