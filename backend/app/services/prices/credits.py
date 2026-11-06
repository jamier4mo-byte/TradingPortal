"""Each user's daily Twelve Data credits (`price_credit_usage`). Twelve Data's day is the UTC date.

800 credits a day on the Basic plan, reset at 00:00 UTC. At 800 the user is paused: they see the last
cached prices marked stale until the reset. A 429 "for the day" answer pauses them too, whatever our
counter says. `/api_usage` answers correct the counter upwards (we never lower it: a lower provider
figure would just mean another app shares the key).
"""

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session

from ...models import PriceCreditUsage

DAILY_LIMIT = 800
PAUSED_REASON = "Live data paused – daily limit reached"


def day_of(now: datetime) -> date:
    return now.astimezone(UTC).date()


def resets_at(now: datetime) -> datetime:
    return datetime.combine(day_of(now) + timedelta(days=1), time(0, 0), tzinfo=UTC)


def row(db: Session, user_id: int, now: datetime) -> PriceCreditUsage | None:
    return db.get(PriceCreditUsage, (user_id, day_of(now)))


def _row_for_update(db: Session, user_id: int, now: datetime) -> PriceCreditUsage:
    r = row(db, user_id, now)
    if r is None:
        r = PriceCreditUsage(user_id=user_id, day=day_of(now), credits=0, background_credits=0, requests=0)
        db.add(r)
    return r


def used(db: Session, user_id: int, now: datetime) -> int:
    r = row(db, user_id, now)
    return r.credits if r else 0


def background_used(db: Session, user_id: int, now: datetime) -> int:
    r = row(db, user_id, now)
    return r.background_credits if r else 0


def paused(db: Session, user_id: int, now: datetime) -> bool:
    return used(db, user_id, now) >= DAILY_LIMIT


def charge(db: Session, user_id: int, credits: int, now: datetime, *, background: bool = False) -> None:
    r = _row_for_update(db, user_id, now)
    r.credits = (r.credits or 0) + credits
    r.requests = (r.requests or 0) + 1
    if background:
        r.background_credits = (r.background_credits or 0) + credits
    r.updated_at = now
    db.commit()


def mark_exhausted(db: Session, user_id: int, now: datetime) -> None:
    """Twelve Data said the day's credits are gone: pause until 00:00 UTC."""
    r = _row_for_update(db, user_id, now)
    r.credits = max(r.credits or 0, DAILY_LIMIT)
    r.updated_at = now
    db.commit()


def record_reported(db: Session, user_id: int, reported: int | None, now: datetime) -> int:
    """Store `/api_usage`'s daily figure and correct our counter upwards. Returns credits used today."""
    r = _row_for_update(db, user_id, now)
    if reported is not None:
        r.provider_reported = reported
        r.credits = max(r.credits or 0, reported)
    r.updated_at = now
    db.commit()
    return r.credits
