"""Analytics API (2.4, F16): one query endpoint for the Ideal, Backtest and Compare views."""

from fastapi import APIRouter, HTTPException

from ..core.deps import CurrentUser, Db
from ..schemas.analytics import AnalyticsQuery
from ..services.analytics.metrics import registry_meta
from ..services.analytics.query import run_query
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
