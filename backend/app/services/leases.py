"""Leases and rate slots shared by every process through the database.

Two uses:
- `hold(name, holder, ttl)`: a renewable lease. The scheduler holds "scheduler" so only one process
  ticks; another process takes over once the holder stops renewing and the lease expires.
- `claim_slot(name, interval)`: a global rate slot. At most one claim per `interval`, whoever asks
  (JBlanked: one request every 5 minutes across every process).

Both are a single conditional UPDATE (or an INSERT that the primary key makes exclusive), so two
processes can't both win: SQLite serialises writers.
"""

from datetime import datetime, timedelta

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Lease, utcnow


def _claim(db: Session, name: str, holder: str, until: datetime, now: datetime, *, renew: bool) -> bool:
    cond = Lease.expires_at <= now
    if renew:
        cond = cond | (Lease.holder == holder)
    res = db.execute(update(Lease).where(Lease.name == name, cond).values(holder=holder, expires_at=until))
    if res.rowcount:
        db.commit()
        return True
    if db.scalar(select(Lease.name).where(Lease.name == name)) is not None:
        db.rollback()
        return False
    try:
        db.execute(insert(Lease).values(name=name, holder=holder, expires_at=until))
        db.commit()
        return True
    except IntegrityError:  # another process inserted it first
        db.rollback()
        return False


def hold(db: Session, name: str, holder: str, ttl: timedelta, now: datetime | None = None) -> bool:
    """Take or renew a lease. True if `holder` now holds it until now + ttl."""
    now = now or utcnow()
    return _claim(db, name, holder, now + ttl, now, renew=True)


def release(db: Session, name: str, holder: str) -> None:
    db.execute(
        update(Lease)
        .where(Lease.name == name, Lease.holder == holder)
        .values(expires_at=datetime(2000, 1, 1, tzinfo=utcnow().tzinfo))
    )
    db.commit()


def claim_slot(
    db: Session, name: str, interval: timedelta, now: datetime | None = None, holder: str = "slot"
) -> bool:
    """True at most once per `interval` for `name`, across every process."""
    now = now or utcnow()
    return _claim(db, name, holder, now + interval, now, renew=False)


def next_slot_at(db: Session, name: str) -> datetime | None:
    return db.scalar(select(Lease.expires_at).where(Lease.name == name))
