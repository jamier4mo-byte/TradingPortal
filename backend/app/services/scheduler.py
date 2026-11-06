"""The in-app scheduler (F7): one asyncio task started in FastAPI's lifespan, ticking every minute.

Only one process ticks: each tick first takes or renews the "scheduler" lease in the database.
Each job is a plain function `job(db, now) -> dict | None`, run in order inside a worker thread;
one failing job is logged and never stops the others.

Jobs (all safe to call every minute; each decides for itself whether there's work to do):
  news.feeds        Forex Factory hourly, JBlanked within its slot and daily budget
  news.tagging      re-tag trades when coverage has grown
  alerts            Web Push notifications that are due
  prices.reactions  price reactions after releases, with opted-in leftover credits
"""

import asyncio
import importlib
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..core.settings import get_settings
from ..db import session_factory
from ..models import utcnow
from . import leases

log = logging.getLogger("trading_portal.scheduler")

LEASE = "scheduler"
HOLDER = f"proc-{uuid.uuid4().hex[:12]}"

# (name, "module:function"). Imported lazily so a job module can't stop the app from starting.
JOBS: list[tuple[str, str]] = [
    ("news.feeds", "app.services.news.jobs:refresh_feeds"),
    ("news.tagging", "app.services.news.tagging:retag_if_coverage_grew"),
    ("alerts", "app.services.alerts:run_due"),
    ("prices.reactions", "app.services.prices.reactions:run"),
]


def _resolve(target: str) -> Callable[[Session, datetime], dict | None]:
    module, _, name = target.partition(":")
    return getattr(importlib.import_module(module), name)


def tick(
    db: Session, now: datetime | None = None, holder: str = HOLDER, jobs: list[tuple[str, str]] | None = None
) -> dict:
    """One tick. Returns what ran, for logs and tests. Skips everything if another process holds the lease."""
    now = now or utcnow()
    ttl = timedelta(seconds=max(get_settings().scheduler_tick_seconds * 3, 120))
    if not leases.hold(db, LEASE, holder, ttl, now):
        return {"skipped": "lease held by another process"}
    results: dict = {}
    for name, target in jobs if jobs is not None else JOBS:
        try:
            results[name] = _resolve(target)(db, now)
        except Exception as exc:  # noqa: BLE001 — one job's failure must never stop the rest
            db.rollback()
            log.exception("scheduler job %s failed", name)
            results[name] = {"error": type(exc).__name__}
    return results


def _tick_once() -> None:
    with session_factory()() as db:
        tick(db)


async def run_forever() -> None:
    seconds = get_settings().scheduler_tick_seconds
    log.info("scheduler started (%s, every %ss)", HOLDER, seconds)
    while True:
        try:
            await asyncio.to_thread(_tick_once)
        except Exception:  # noqa: BLE001
            log.exception("scheduler tick failed")
        await asyncio.sleep(seconds)


def should_run() -> bool:
    s = get_settings()
    return s.scheduler and s.env != "test"
