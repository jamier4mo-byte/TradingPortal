"""Analytics API (2.4, F16): one query endpoint for the Ideal, Backtest and Compare views."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from ..core.deps import CurrentUser, Db, HeavyUser
from ..schemas.analytics import AnalyticsQuery, ExportQuery
from ..services import journal as journal_svc
from ..services.analytics import export as export_svc
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


def _parse(q: str) -> ExportQuery:
    """Exports are plain GET downloads (the browser streams them to disk); the query rides in `q` as JSON."""
    try:
        return ExportQuery.model_validate_json(q or "{}")
    except ValidationError as exc:
        raise HTTPException(422, "The export filters aren't valid.") from exc


def _check_strategy(db, q: AnalyticsQuery) -> None:
    if q.strategy_id is not None:
        try:
            journal_svc.get_strategy(db, q.strategy_id)
        except JournalError as exc:
            raise HTTPException(exc.status, exc.message) from exc


def _attachment(name: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"}


@router.get("/analytics/export/ai")
def export_for_ai(user: HeavyUser, db: Db, q: str = Query("{}", max_length=8000)) -> StreamingResponse:
    """Export for AI (F8): a zip of trades.jsonl, images/, strategy.md, README_prompt.md and manifest.json."""
    query = _parse(q)
    _check_strategy(db, query)
    body = export_svc.stream_ai_zip(db, user, query)
    name = export_svc.export_filename(db, query, "zip")
    return StreamingResponse(body, media_type="application/zip", headers=_attachment(name))


@router.get("/analytics/export/csv")
def export_csv(user: HeavyUser, db: Db, q: str = Query("{}", max_length=8000)) -> StreamingResponse:
    """The filtered trades as CSV (UTF-8 with a BOM for Excel)."""
    query = _parse(q)
    _check_strategy(db, query)
    body = export_svc.stream_csv(db, user, query)
    name = export_svc.export_filename(db, query, "csv")
    return StreamingResponse(body, media_type="text/csv; charset=utf-8", headers=_attachment(name))


@router.post("/analytics/copy")
def copy_for_ai(body: AnalyticsQuery, user: CurrentUser, db: Db) -> dict:
    """Copy for AI: strategy.md plus a compact KPI and trade summary for the clipboard."""
    _check_strategy(db, body)
    return export_svc.copy_text(db, user, body)
