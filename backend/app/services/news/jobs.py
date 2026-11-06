"""The scheduler's news job: `refresh_feeds(db, now)`, called every minute.

Cheap when there's nothing to do (one or two small queries), and never touches the network unless
`settings.feeds_live` (feeds = live and not under tests). The two feeds run independently: one failing
is logged on its `feed_runs` row and the other still keeps the calendar up to date.
"""

import logging
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from ...core.settings import get_settings
from . import ff, jblanked

log = logging.getLogger("trading_portal.news.jobs")


def refresh_feeds(
    db: Session,
    now: datetime,
    *,
    live: bool | None = None,
    ff_transport: httpx.BaseTransport | None = None,
    jb_transport: httpx.BaseTransport | None = None,
) -> dict:
    """`live` overrides `settings.feeds_live` (tests pass True with mock transports)."""
    if not (get_settings().feeds_live if live is None else live):
        return {"skipped": "feeds off"}
    out: dict = {}
    for name, step, transport in (
        (ff.FEED, ff.refresh_if_due, ff_transport),
        (jblanked.FEED, jblanked.refresh_if_due, jb_transport),
    ):
        try:
            out[name] = step(db, now, transport)
        except Exception as exc:  # noqa: BLE001 — one feed failing never stops the other
            db.rollback()
            log.exception("news feed %s failed", name)
            out[name] = {"status": "error", "error": type(exc).__name__}
    return out
