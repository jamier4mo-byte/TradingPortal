"""Team calendar services (1.4): expand recurring tasks, create / edit / move / delete / complete.

Times are stored in UTC. Recurrence expands with dateutil in the task's own zone (`tz`), then each
occurrence is converted to UTC, so a weekly 09:00 Europe/London task stays 09:00 UK across the clock
changes (29 Mar 2026, 25 Oct 2026). All-day tasks live on local dates.

An occurrence is identified by its task and the *original* local date it was generated for
(`occurrence_date`, YYYY-MM-DD). Moving an occurrence keeps that key, so its exception and completion
rows still find it; what changes is where it is shown.
"""

import logging
import re
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil import rrule as du
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.deps import require_owner_or_admin
from ..core.security import utcnow
from ..models import CATEGORIES, CATEGORY_LABELS, DEFAULT_TZ, Task, TaskCompletion, TaskException, User
from . import audit

MAX_RANGE_DAYS = 62
# A moved occurrence can land this far from its original date and still be found by expansion.
PAD = timedelta(days=45)
Mode = str  # "series" | "occurrence"
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


log = logging.getLogger("trading_portal.calendar")


class CalendarError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


# ---- validation helpers ----------------------------------------------------------------------


def resolve_zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise CalendarError(f"{name!r} is not a time zone.", 422) from exc


def normalise_rrule(text: str | None) -> str | None:
    """Upper-case, drop a leading `RRULE:` and read UNTIL as local wall time (a trailing Z is dropped)."""
    if text is None:
        return None
    rule = text.strip()
    if not rule:
        return None
    if rule.upper().startswith("RRULE:"):
        rule = rule[6:]
    rule = rule.upper().replace(" ", "")
    rule = re.sub(r"(UNTIL=\d{8}T\d{6})Z", r"\1", rule)
    return rule


# Only these characters may appear in a stored rule: no whitespace or line breaks, so nothing can smuggle a
# DTSTART/RDATE/EXDATE line past the parser, and nothing but the RRULE grammar is ever evaluated.
RRULE_CHARS = re.compile(r"[A-Z0-9=;,+\-]+")
# The most occurrences one task may contribute to a single expansion window (62 days, daily at most).
MAX_OCCURRENCES_PER_TASK = 200
# A repeating task's start may be at most this many years from today (bounds the expansion walk).
MAX_RRULE_YEARS = 10


def parse_rrule(rule: str, dtstart: datetime, *, for_write: bool = False) -> du.rrule:
    """`dtstart` is a naive local datetime; a bad rule raises CalendarError(422).

    With `for_write` (create and series edits) the policy that keeps expansion cheap also applies: daily is
    the finest repeat, no BYHOUR/BYMINUTE/BYSECOND/BYSETPOS, and the start within MAX_RRULE_YEARS of today.
    The read path only parses, so a rule that was valid when written can never take the calendar down later.
    """
    if not RRULE_CHARS.fullmatch(rule) or "DTSTART" in rule or "RDATE" in rule or "EXDATE" in rule:
        raise CalendarError("That repeat rule has characters or parts that aren't allowed.", 422)
    try:
        parsed = du.rrulestr(f"RRULE:{rule}", dtstart=dtstart)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise CalendarError(
            "That repeat rule doesn't parse. Use RRULE syntax, e.g. FREQ=WEEKLY;BYDAY=MO.", 422
        ) from exc
    if not isinstance(parsed, du.rrule):
        raise CalendarError("Use a single RRULE (no RDATE or EXDATE).", 422)
    if not for_write:
        return parsed
    # Sub-daily rules would expand to thousands of rows inside the 62-day window (a denial of service);
    # the calendar is about days and sessions, so daily is the finest repeat.
    if parsed._freq > du.DAILY:  # noqa: SLF001 — dateutil keeps the frequency private
        raise CalendarError("Repeat at most once a day (FREQ=DAILY, WEEKLY, MONTHLY or YEARLY).", 422)
    # BYHOUR/BYMINUTE/BYSECOND multiply a daily rule into many rows a day, and BYSETPOS has no use here.
    if re.search(r"(^|;)(BYHOUR|BYMINUTE|BYSECOND|BYSETPOS)=", rule):
        raise CalendarError("Repeat rules can't use BYHOUR, BYMINUTE, BYSECOND or BYSETPOS.", 422)
    # Expansion walks from the rule's start to the window, so a start decades away costs time for nothing.
    anchor = parsed._dtstart  # noqa: SLF001 — the start dateutil really uses
    if abs(anchor.year - datetime.now(UTC).year) > MAX_RRULE_YEARS:
        raise CalendarError(f"A repeating task must start within {MAX_RRULE_YEARS} years of today.", 422)
    return parsed


# The most occurrences one task may contribute to a single expansion window (62 days, daily at most).
MAX_OCCURRENCES_PER_TASK = 200


def check_category(value: str | None) -> str:
    key = (value or "other").strip().lower()
    if key not in CATEGORIES:
        raise CalendarError("Category must be one of Backtesting, Review, Admin or Other.", 422)
    return key


def check_occurrence_date(value: str | None) -> str:
    if not value or not _DATE.match(value):
        raise CalendarError("occurrence_date must be YYYY-MM-DD.", 422)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise CalendarError("occurrence_date must be a real date.", 422) from exc
    return value


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _local_naive(dt: datetime, zone: ZoneInfo) -> datetime:
    return _aware(dt).astimezone(zone).replace(tzinfo=None)


def _to_utc(local_naive: datetime, zone: ZoneInfo) -> datetime:
    return local_naive.replace(tzinfo=zone).astimezone(UTC)


def _midnight(d: date, zone: ZoneInfo) -> datetime:
    return _to_utc(datetime.combine(d, time(0)), zone)


def _normalise_times(
    *, all_day: bool, start_at: datetime, end_at: datetime | None, zone: ZoneInfo
) -> tuple[datetime, datetime | None]:
    start = _aware(start_at)
    end = _aware(end_at) if end_at else None
    if all_day:
        local = start.astimezone(zone)
        start = _midnight(local.date(), zone)
        if end:
            local_end = end.astimezone(zone)
            end_day = (
                local_end.date() if local_end.time() == time(0) else local_end.date() + timedelta(days=1)
            )
            if end_day <= local.date():
                end_day = local.date() + timedelta(days=1)
            end = _midnight(end_day, zone)
    elif end is not None and end <= start:
        raise CalendarError("The end must be after the start.", 422)
    return start, end


# ---- expansion ---------------------------------------------------------------------------------


def _owner_dict(user: User | None) -> dict:
    if user is None:
        return {
            "id": 0,
            "display_name": "Unknown",
            "label": "Unknown",
            "status": "deactivated",
            "colour_index": 0,
        }
    return {
        "id": user.id,
        "display_name": user.display_name,
        "label": user.label,
        "status": user.status,
        "colour_index": user.colour_index,
    }


def _occurrence_dates(task: Task, zone: ZoneInfo, lo: datetime, hi: datetime) -> list[datetime]:
    """Local naive start datetimes the task produces inside the local window [lo, hi] (padded by caller)."""
    local_start = _local_naive(task.start_at, zone)
    if not task.rrule:
        return [local_start] if lo <= local_start <= hi else []
    try:
        rule = parse_rrule(task.rrule, local_start)
    except CalendarError:  # one bad row must never take the whole calendar down
        log.warning("task %s has an unreadable repeat rule; skipped", task.id)
        return []
    out: list[datetime] = []
    for hit in rule.xafter(lo - timedelta(seconds=1), count=MAX_OCCURRENCES_PER_TASK, inc=False):
        if hit > hi:
            break
        out.append(hit)
    return out


def _series_occurrence_start(task: Task, zone: ZoneInfo, occurrence_date: str) -> datetime | None:
    """UTC start of the occurrence originally generated on `occurrence_date`, or None if there isn't one."""
    d = date.fromisoformat(occurrence_date)
    local_start = _local_naive(task.start_at, zone)
    if not task.rrule:
        return task.start_at if local_start.date() == d else None
    try:
        rule = parse_rrule(task.rrule, local_start)
    except CalendarError:
        return None
    hits = rule.between(datetime.combine(d, time(0)), datetime.combine(d, time(23, 59, 59)), inc=True)
    return _to_utc(hits[0], zone) if hits else None


def _duration(task: Task, zone: ZoneInfo) -> timedelta | None:
    if task.end_at is None:
        return None
    if task.all_day:
        days = (_local_naive(task.end_at, zone).date() - _local_naive(task.start_at, zone).date()).days
        return timedelta(days=max(days, 1))
    return _aware(task.end_at) - _aware(task.start_at)


def expand(
    db: Session,
    start: datetime,
    end: datetime,
    owners: list[int] | None = None,
    *,
    viewer: User | None = None,
) -> list[dict]:
    """Occurrences with a start in [start, end) (UTC), oldest first. At most MAX_RANGE_DAYS."""
    start, end = _aware(start), _aware(end)
    if end <= start:
        raise CalendarError("`to` must be after `from`.", 422)
    if end - start > timedelta(days=MAX_RANGE_DAYS):
        raise CalendarError(f"Ask for at most {MAX_RANGE_DAYS} days at a time.", 422)

    stmt = select(Task).where(Task.deleted_at.is_(None))
    if owners:
        stmt = stmt.where(Task.owner_id.in_(owners))
    tasks = list(db.scalars(stmt))
    if not tasks:
        return []
    ids = [t.id for t in tasks]
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({t.owner_id for t in tasks})))}
    exceptions: dict[tuple[int, str], TaskException] = {
        (e.task_id, e.occurrence_date): e
        for e in db.scalars(select(TaskException).where(TaskException.task_id.in_(ids)))
    }
    completions: dict[tuple[int, str], TaskCompletion] = {
        (c.task_id, c.occurrence_date): c
        for c in db.scalars(select(TaskCompletion).where(TaskCompletion.task_id.in_(ids)))
    }
    completer_ids = {c.completed_by_id for c in completions.values()} - set(users)
    if completer_ids:
        users.update({u.id: u for u in db.scalars(select(User).where(User.id.in_(completer_ids)))})

    out: list[dict] = []
    for task in tasks:
        zone = resolve_zone(task.tz)
        duration = _duration(task, zone)
        lo = _local_naive(start - PAD, zone)
        hi = _local_naive(end + PAD, zone)
        seen: set[str] = set()
        candidates: list[tuple[str, datetime]] = []
        for local in _occurrence_dates(task, zone, lo, hi):
            key = local.date().isoformat()
            if key in seen:
                continue
            seen.add(key)
            occ_start = _midnight(local.date(), zone) if task.all_day else _to_utc(local, zone)
            candidates.append((key, occ_start))
        # Occurrences moved from far outside the padded window still have an exception row here.
        for (tid, key), exc in exceptions.items():
            if tid == task.id and key not in seen and exc.start_at is not None and not exc.deleted:
                seen.add(key)
                candidates.append((key, exc.start_at))

        for key, occ_start in candidates:
            exc = exceptions.get((task.id, key)) if task.rrule else None
            if exc and exc.deleted:
                continue
            all_day = exc.all_day if exc and exc.all_day is not None else task.all_day
            s = _aware(exc.start_at) if exc and exc.start_at else occ_start
            if exc and exc.end_at:
                e: datetime | None = _aware(exc.end_at)
            elif duration is None:
                e = None
            elif all_day:
                e = _midnight(s.astimezone(zone).date() + duration, zone)
            else:
                e = s + duration
            if not (start <= s < end):
                continue
            done = completions.get((task.id, key))
            owner = users.get(task.owner_id)
            out.append(
                {
                    "id": f"{task.id}:{key}",
                    "task_id": task.id,
                    "occurrence_date": key,
                    "start_at": s,
                    "end_at": e,
                    "all_day": all_day,
                    "title": exc.title if exc and exc.title else task.title,
                    "description": exc.description
                    if exc and exc.description is not None
                    else task.description,
                    "category": exc.category if exc and exc.category else task.category,
                    "category_label": CATEGORY_LABELS.get(
                        exc.category if exc and exc.category else task.category, "Other"
                    ),
                    "tz": task.tz,
                    "owner": _owner_dict(owner),
                    "done": done is not None,
                    "completed_by": _owner_dict(users.get(done.completed_by_id)) if done else None,
                    "completed_at": done.completed_at if done else None,
                    "recurring": bool(task.rrule),
                    "exception": exc is not None,
                    "can_edit": bool(viewer and (viewer.is_admin or task.owner_id == viewer.id)),
                }
            )
    out.sort(key=lambda o: (o["start_at"], o["task_id"]))
    return out


# ---- CRUD ---------------------------------------------------------------------------------------


def live_tasks(db: Session):
    return select(Task).where(Task.deleted_at.is_(None)).order_by(Task.start_at)


def get_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if not task or task.deleted_at:
        raise CalendarError("No such task.", 404)
    return task


def _clean_title(value: str | None) -> str:
    title = (value or "").strip()
    if not title:
        raise CalendarError("Give the task a title.", 422)
    if len(title) > 120:
        raise CalendarError("Keep the title under 120 characters.", 422)
    return title


def create(db: Session, actor: User, **fields) -> Task:
    zone = resolve_zone(fields.get("tz"))
    all_day = bool(fields.get("all_day", False))
    start_at = fields.get("start_at")
    if start_at is None:
        raise CalendarError("A start is required.", 422)
    start, end = _normalise_times(all_day=all_day, start_at=start_at, end_at=fields.get("end_at"), zone=zone)
    rule = normalise_rrule(fields.get("rrule"))
    if rule:
        parse_rrule(rule, _local_naive(start, zone), for_write=True)
    task = Task(
        owner_id=actor.id,
        title=_clean_title(fields.get("title")),
        description=(fields.get("description") or "").strip() or None,
        category=check_category(fields.get("category")),
        all_day=all_day,
        start_at=start,
        end_at=end,
        tz=zone.key,
        rrule=rule,
    )
    db.add(task)
    db.flush()
    audit.record(db, "task.created", actor=actor, target_type="task", target_id=task.id)
    db.commit()
    return task


def _exception_for(db: Session, task: Task, occurrence_date: str, zone: ZoneInfo) -> TaskException:
    key = check_occurrence_date(occurrence_date)
    existing = db.scalar(
        select(TaskException).where(TaskException.task_id == task.id, TaskException.occurrence_date == key)
    )
    if existing:
        return existing
    if _series_occurrence_start(task, zone, key) is None:
        raise CalendarError("That task has no occurrence on that date.", 404)
    now = utcnow()
    exc = TaskException(task_id=task.id, occurrence_date=key, created_at=now, updated_at=now)
    db.add(exc)
    db.flush()
    return exc


def _occurrence_current_start(db: Session, task: Task, zone: ZoneInfo, key: str) -> datetime:
    """Where the occurrence is shown now (its exception's start if it was moved)."""
    exc = db.scalar(
        select(TaskException).where(TaskException.task_id == task.id, TaskException.occurrence_date == key)
    )
    if exc and exc.start_at:
        return _aware(exc.start_at)
    base = _series_occurrence_start(task, zone, key)
    if base is None:
        raise CalendarError("That task has no occurrence on that date.", 404)
    return base


def _shift_local(dt: datetime, delta: timedelta, zone: ZoneInfo) -> datetime:
    """Shift by a wall-clock delta (so 09:00 stays 09:00 across a clock change)."""
    return _to_utc(_local_naive(dt, zone) + delta, zone)


def update(
    db: Session,
    actor: User,
    task: Task,
    *,
    mode: Mode = "series",
    occurrence_date: str | None = None,
    **fields,
) -> Task:
    require_owner_or_admin(task, actor)
    fields = {k: v for k, v in fields.items() if k in UPDATABLE}
    zone = resolve_zone(fields.get("tz") or task.tz)
    if "title" in fields:
        fields["title"] = _clean_title(fields["title"])
    if "category" in fields:
        fields["category"] = check_category(fields["category"])
    if "description" in fields:
        fields["description"] = (fields["description"] or "").strip() or None

    if task.rrule and mode == "occurrence":
        if not occurrence_date:
            raise CalendarError("Say which occurrence (occurrence_date).", 422)
        if "rrule" in fields or "tz" in fields:
            raise CalendarError("Change the repeat rule or zone on the whole series.", 422)
        exc = _exception_for(db, task, occurrence_date, zone)
        all_day = fields.get("all_day", exc.all_day if exc.all_day is not None else task.all_day)
        if "start_at" in fields or "end_at" in fields or "all_day" in fields:
            cur_start = (
                _aware(exc.start_at)
                if exc.start_at
                else _occurrence_current_start(db, task, zone, exc.occurrence_date)
            )
            duration = (_aware(exc.end_at) - cur_start) if exc.end_at else _duration(task, zone)
            new_start = _aware(fields["start_at"]) if fields.get("start_at") else cur_start
            if "end_at" in fields:
                new_end = _aware(fields["end_at"]) if fields["end_at"] else None
            elif duration is None:
                new_end = None
            elif all_day:
                new_end = _midnight(new_start.astimezone(zone).date() + duration, zone)
            else:
                new_end = new_start + duration
            exc.start_at, exc.end_at = _normalise_times(
                all_day=all_day, start_at=new_start, end_at=new_end, zone=zone
            )
            exc.all_day = all_day
        for key in ("title", "description", "category"):
            if key in fields:
                setattr(exc, key, fields[key])
        exc.updated_at = utcnow()
        audit.record(
            db,
            "task.occurrence_updated",
            actor=actor,
            target_type="task",
            target_id=task.id,
            meta={"occurrence_date": exc.occurrence_date},
        )
        db.commit()
        return task

    # Whole series (or a one-off task: mode is ignored).
    if "rrule" in fields:
        task.rrule = normalise_rrule(fields["rrule"])
    if "tz" in fields:
        task.tz = zone.key
    all_day = bool(fields.get("all_day", task.all_day))
    if "start_at" in fields or "end_at" in fields or "all_day" in fields:
        duration = _duration(task, zone)
        new_start = _aware(task.start_at)
        if fields.get("start_at"):
            wanted = _aware(fields["start_at"])
            if task.rrule and occurrence_date:
                # Dragging one occurrence of the series: shift the whole series by that wall-clock delta.
                base = _series_occurrence_start(task, zone, check_occurrence_date(occurrence_date))
                if base is None:
                    raise CalendarError("That task has no occurrence on that date.", 404)
                delta = _local_naive(wanted, zone) - _local_naive(base, zone)
                new_start = _shift_local(task.start_at, delta, zone)
            else:
                new_start = wanted
        if "end_at" in fields:
            new_end = _aware(fields["end_at"]) if fields["end_at"] else None
            if new_end is not None and fields.get("start_at") and task.rrule and occurrence_date:
                # The end came with a moved occurrence: keep it as a duration from the new start.
                new_end = new_start + (new_end - _aware(fields["start_at"]))
        elif duration is None:
            new_end = None
        elif all_day:
            new_end = _midnight(new_start.astimezone(zone).date() + duration, zone)
        else:
            new_end = new_start + duration
        task.start_at, task.end_at = _normalise_times(
            all_day=all_day, start_at=new_start, end_at=new_end, zone=zone
        )
        task.all_day = all_day
    if task.rrule:
        parse_rrule(task.rrule, _local_naive(task.start_at, zone), for_write=True)
    for key in ("title", "description", "category"):
        if key in fields:
            setattr(task, key, fields[key])
    audit.record(db, "task.updated", actor=actor, target_type="task", target_id=task.id)
    db.commit()
    return task


UPDATABLE = {"title", "description", "category", "all_day", "start_at", "end_at", "tz", "rrule"}


def move(
    db: Session,
    actor: User,
    task: Task,
    new_start: datetime,
    *,
    mode: Mode = "series",
    occurrence_date: str | None = None,
    new_end: datetime | None = None,
) -> Task:
    fields: dict = {"start_at": new_start}
    if new_end is not None:
        fields["end_at"] = new_end
    return update(db, actor, task, mode=mode, occurrence_date=occurrence_date, **fields)


def delete(
    db: Session, actor: User, task: Task, *, mode: Mode = "series", occurrence_date: str | None = None
) -> None:
    require_owner_or_admin(task, actor)
    if task.rrule and mode == "occurrence":
        if not occurrence_date:
            raise CalendarError("Say which occurrence (occurrence_date).", 422)
        exc = _exception_for(db, task, occurrence_date, resolve_zone(task.tz))
        exc.deleted = True
        exc.updated_at = utcnow()
        audit.record(
            db,
            "task.occurrence_deleted",
            actor=actor,
            target_type="task",
            target_id=task.id,
            meta={"occurrence_date": exc.occurrence_date},
        )
        db.commit()
        return
    task.deleted_at = utcnow()
    audit.record(db, "task.deleted", actor=actor, target_type="task", target_id=task.id)
    db.commit()


def complete(db: Session, actor: User, task: Task, occurrence_date: str) -> TaskCompletion:
    """Mark one occurrence done. Idempotent. Members complete their own tasks; the admin anyone's."""
    require_owner_or_admin(task, actor)
    key = check_occurrence_date(occurrence_date)
    existing = db.scalar(
        select(TaskCompletion).where(TaskCompletion.task_id == task.id, TaskCompletion.occurrence_date == key)
    )
    if existing:
        return existing
    zone = resolve_zone(task.tz)
    exc = db.scalar(
        select(TaskException).where(TaskException.task_id == task.id, TaskException.occurrence_date == key)
    )
    if (exc is None or exc.start_at is None) and _series_occurrence_start(task, zone, key) is None:
        raise CalendarError("That task has no occurrence on that date.", 404)
    row = TaskCompletion(
        task_id=task.id, occurrence_date=key, completed_by_id=actor.id, completed_at=utcnow()
    )
    db.add(row)
    audit.record(
        db,
        "task.completed",
        actor=actor,
        target_type="task",
        target_id=task.id,
        meta={"occurrence_date": key},
    )
    db.commit()
    return row


def uncomplete(db: Session, actor: User, task: Task, occurrence_date: str) -> None:
    require_owner_or_admin(task, actor)
    key = check_occurrence_date(occurrence_date)
    existing = db.scalar(
        select(TaskCompletion).where(TaskCompletion.task_id == task.id, TaskCompletion.occurrence_date == key)
    )
    if existing:
        db.delete(existing)
        audit.record(
            db,
            "task.uncompleted",
            actor=actor,
            target_type="task",
            target_id=task.id,
            meta={"occurrence_date": key},
        )
        db.commit()
