"""Push alerts before news events (Foundations 3.5, F7).

- Preferences per user (a missing row means alerts are off).
- Web Push subscriptions per device, upserted by endpoint.
- `run_due(db, now)`: the scheduler's "alerts" job, every minute. Each (device, event) gets at most one
  notification: the `alert_deliveries` row is inserted (and committed) before the send, and its unique
  constraint makes that safe across processes.
"""

import hashlib
import math
import re
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import AlertDelivery, AlertPrefs, Event, PushSubscription, User, utcnow
from . import market_prefs, push

UK = ZoneInfo("Europe/London")

DEFAULT_MINUTES_BEFORE = 15
MIN_MINUTES_BEFORE, MAX_MINUTES_BEFORE = 1, 120
ALERT_IMPACTS = ("high", "medium", "low")
IMPACT_LABELS = {"high": "High", "medium": "Med", "low": "Low"}
# A missed alert moment (restart, slow tick) is still sent up to this long afterwards, never later.
LATE_GRACE = timedelta(minutes=10)
QUIET_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

NO_VAPID = "Push isn't set up on the server yet (VAPID keys missing)."


class AlertError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


# ---- preferences -------------------------------------------------------------------------------


def get_prefs(db: Session, user: User | int) -> AlertPrefs:
    """The user's row, or an unsaved row holding the defaults (alerts off)."""
    user_id = user if isinstance(user, int) else user.id
    row = db.get(AlertPrefs, user_id)
    if row is None:
        row = AlertPrefs(
            user_id=user_id,
            enabled=False,
            minutes_before=DEFAULT_MINUTES_BEFORE,
            currencies=None,
            impacts=["high"],
            quiet_start=None,
            quiet_end=None,
            chime=False,
        )
    return row


def effective_currencies(db: Session, prefs: AlertPrefs) -> set[str]:
    """The chosen currencies, or (None) the currencies of the user's followed instruments."""
    if prefs.currencies is not None:
        return {c.upper() for c in prefs.currencies}
    return market_prefs.currencies_for(db, market_prefs.get_prefs(db, prefs.user_id).instruments)


def _clean_currencies(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    out: list[str] = []
    for raw in value:
        code = raw.strip().upper()
        if not re.fullmatch(r"[A-Z]{2,8}", code):
            raise AlertError(422, f"“{raw}” isn't a currency code.")
        if code not in out:
            out.append(code)
    if not out:
        raise AlertError(422, "Pick at least one currency, or follow your instruments' currencies.")
    return out


def _clean_impacts(value: list[str]) -> list[str]:
    impacts = [i.strip().lower() for i in value]
    bad = [i for i in impacts if i not in ALERT_IMPACTS]
    if bad:
        raise AlertError(422, "Impacts must be high, medium or low.")
    if not impacts:
        raise AlertError(422, "Pick at least one impact level.")
    return [i for i in ALERT_IMPACTS if i in impacts]


def _clean_quiet(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if not QUIET_RE.match(value):
        raise AlertError(422, "Quiet hours use 24-hour HH:MM, e.g. 22:00.")
    return value


def save_prefs(db: Session, user: User, changes: dict) -> AlertPrefs:
    """Apply `changes` (only the keys present). Raises AlertError(422) on bad values."""
    row = db.get(AlertPrefs, user.id)
    if row is None:
        row = get_prefs(db, user)
        db.add(row)
    if "minutes_before" in changes and changes["minutes_before"] is not None:
        minutes = int(changes["minutes_before"])
        if not MIN_MINUTES_BEFORE <= minutes <= MAX_MINUTES_BEFORE:
            raise AlertError(422, f"Minutes before must be {MIN_MINUTES_BEFORE}–{MAX_MINUTES_BEFORE}.")
        row.minutes_before = minutes
    if "currencies" in changes:
        row.currencies = _clean_currencies(changes["currencies"])
    if "impacts" in changes and changes["impacts"] is not None:
        row.impacts = _clean_impacts(changes["impacts"])
    quiet_start = _clean_quiet(changes["quiet_start"]) if "quiet_start" in changes else row.quiet_start
    quiet_end = _clean_quiet(changes["quiet_end"]) if "quiet_end" in changes else row.quiet_end
    if (quiet_start is None) != (quiet_end is None):
        raise AlertError(422, "Set both a quiet-hours start and end, or neither.")
    row.quiet_start, row.quiet_end = quiet_start, quiet_end
    for flag in ("enabled", "chime"):
        if flag in changes and changes[flag] is not None:
            setattr(row, flag, bool(changes[flag]))
    db.commit()
    return row


def in_quiet_hours(prefs: AlertPrefs, now: datetime) -> bool:
    """UK local time within [quiet_start, quiet_end). The window may wrap midnight (22:00–07:00)."""
    if not prefs.quiet_start or not prefs.quiet_end:
        return False
    start, end = time.fromisoformat(prefs.quiet_start), time.fromisoformat(prefs.quiet_end)
    if start == end:
        return False
    local = now.astimezone(UK).time().replace(second=0, microsecond=0)
    if start < end:
        return start <= local < end
    return local >= start or local < end


# ---- subscriptions -----------------------------------------------------------------------------


def endpoint_hash(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode()).hexdigest()[:12]


def upsert_subscription(
    db: Session,
    user: User,
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    device_label: str | None,
    user_agent: str | None = None,
) -> PushSubscription:
    """One row per endpoint. An endpoint registered again (by anyone) moves to that user."""
    label = (device_label or "").strip()[:80] or "This device"
    row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if row is None:
        row = PushSubscription(endpoint=endpoint, user_id=user.id)
        db.add(row)
    elif row.user_id != user.id:
        # A browser profile changed hands: the old owner's delivery history for it goes too.
        db.execute(delete(AlertDelivery).where(AlertDelivery.subscription_id == row.id))
        row.user_id = user.id
    row.p256dh, row.auth, row.device_label = p256dh, auth, label
    row.user_agent = (user_agent or "")[:300] or None
    row.last_error = None
    db.commit()
    return row


def list_subscriptions(db: Session, user: User | int) -> list[PushSubscription]:
    user_id = user if isinstance(user, int) else user.id
    return list(
        db.scalars(
            select(PushSubscription)
            .where(PushSubscription.user_id == user_id)
            .order_by(PushSubscription.created_at, PushSubscription.id)
        )
    )


def _own_subscription(db: Session, user: User, subscription_id: int) -> PushSubscription:
    row = db.get(PushSubscription, subscription_id)
    if row is None or row.user_id != user.id:
        raise AlertError(404, "That device isn't set up for alerts.")
    return row


def delete_subscription(db: Session, user: User, subscription_id: int) -> None:
    db.delete(_own_subscription(db, user, subscription_id))
    db.commit()


# ---- sending -----------------------------------------------------------------------------------


def _uk_hhmm(at: datetime) -> str:
    return at.astimezone(UK).strftime("%H:%M")


def build_payload(event: Event, now: datetime, chime: bool) -> dict:
    minutes = max(1, math.ceil((event.at - now).total_seconds() / 60))
    parts = [f"{IMPACT_LABELS.get(event.impact, event.impact.title())} impact", f"{_uk_hhmm(event.at)} UK"]
    if event.forecast:
        parts.append(f"forecast {event.forecast}")
    if event.previous:
        parts.append(f"previous {event.previous}")
    return {
        "title": f"{event.currency} {event.title} in {minutes} min",
        "body": " · ".join(parts),
        "url": f"/news/events/{event.id}",
        "tag": f"event-{event.id}",
        "event_id": event.id,
        "chime": bool(chime),
    }


def _claim(db: Session, user_id: int, sub_id: int, event_id: int, status: str, now: datetime) -> int | None:
    """Insert the delivery row (committed). None if another tick or process already has it."""
    row = AlertDelivery(
        user_id=user_id, subscription_id=sub_id, event_id=event_id, status=status, created_at=now
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    return row.id


def _deliver(
    db: Session, sender: push.PushSender, sub: PushSubscription, payload: dict, now: datetime
) -> str:
    """Send to one device and record the outcome on it. Returns "sent" | "pruned" | "failed"."""
    result = sender.send(sub, payload)
    if result.ok:
        sub.last_success_at = now
        sub.last_error = None
        db.commit()
        return "sent"
    if result.gone:
        db.delete(sub)  # its deliveries cascade
        db.commit()
        return "pruned"
    sub.last_error = (result.error or f"Push service answered {result.status_code}")[:300]
    db.commit()
    return "failed"


def _due_events(db: Session, prefs: AlertPrefs, currencies: set[str], now: datetime) -> list[Event]:
    lead = timedelta(minutes=prefs.minutes_before)
    # Alert moment = at − lead. Due when alert moment ≤ now < at, and no more than LATE_GRACE late.
    return list(
        db.scalars(
            select(Event)
            .where(
                Event.at > now,
                Event.at <= now + lead,
                Event.at >= now + lead - LATE_GRACE,
                Event.all_day.is_(False),
                Event.impact.in_([i for i in prefs.impacts if i in ALERT_IMPACTS]),
                Event.currency.in_(sorted(currencies)),
            )
            .order_by(Event.at, Event.id)
        )
    )


def run_due(db: Session, now: datetime | None = None) -> dict:
    """The scheduler job. Sends every alert that's due at `now`; returns counts."""
    now = (now or utcnow()).astimezone(UTC)
    counts = {"users": 0, "sent": 0, "failed": 0, "pruned": 0, "quiet": 0}
    sender = push.get_sender()
    if sender is None:
        return {**counts, "skipped": "push not configured"}
    rows = db.execute(
        select(AlertPrefs, User).join(User, User.id == AlertPrefs.user_id).where(AlertPrefs.enabled.is_(True))
    ).all()
    for prefs, user in rows:
        if not user.is_active:
            continue
        subs = list_subscriptions(db, user.id)
        if not subs:
            continue
        currencies = effective_currencies(db, prefs)
        if not currencies or not prefs.impacts:
            continue
        events = _due_events(db, prefs, currencies, now)
        if not events:
            continue
        counts["users"] += 1
        quiet = in_quiet_hours(prefs, now)
        chime = prefs.chime
        sub_ids = [s.id for s in subs]
        done = {
            (sid, eid)
            for sid, eid in db.execute(
                select(AlertDelivery.subscription_id, AlertDelivery.event_id).where(
                    AlertDelivery.subscription_id.in_(sub_ids),
                    AlertDelivery.event_id.in_([e.id for e in events]),
                )
            )
        }
        for event in events:
            payload = build_payload(event, now, chime)
            for sub_id in sub_ids:
                if (sub_id, event.id) in done:
                    continue
                sub = db.get(PushSubscription, sub_id)
                if sub is None or sub.user_id != user.id:  # pruned or moved meanwhile
                    continue
                status = "skipped_quiet" if quiet else "sent"
                delivery_id = _claim(db, user.id, sub_id, event.id, status, now)
                if delivery_id is None:
                    continue
                if quiet:
                    counts["quiet"] += 1
                    continue
                outcome = _deliver(db, sender, sub, payload, now)
                counts[outcome] += 1
                if outcome == "failed":
                    delivery = db.get(AlertDelivery, delivery_id)
                    if delivery is not None:
                        delivery.status = "failed"
                        db.commit()
    return counts


def send_test(db: Session, user: User, subscription_id: int | None = None) -> dict:
    """A test notification to one or all of the user's devices. Prunes dead ones."""
    sender = push.get_sender()
    if sender is None:
        raise AlertError(503, NO_VAPID)
    subs = [_own_subscription(db, user, subscription_id)] if subscription_id else list_subscriptions(db, user)
    if not subs:
        raise AlertError(409, "No devices are set up for alerts yet. Turn on alerts on this device first.")
    now = utcnow()
    payload = {
        "title": "Test alert · Trading Portal",
        "body": "Alerts are working on this device.",
        "url": "/settings/alerts",
        "tag": "test-alert",
        "event_id": None,
        "chime": get_prefs(db, user).chime,
    }
    counts = {"sent": 0, "failed": 0, "pruned": 0}
    for sub in subs:
        counts[_deliver(db, sender, sub, payload, now)] += 1
    return counts
