"""Team calendar API (1.4): occurrences for a date range, tasks CRUD, per-occurrence edits, completions.

Dates in the query string are UK calendar dates (Europe/London); `to` is inclusive, like the News Room.
Everyone reads everyone's tasks (4.1); members change only their own, the admin anything.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..core.deps import CurrentUser, Db, ScopeParam, apply_scope
from ..models import CATEGORY_LABELS, Task, TaskCompletion, User
from ..schemas.auth import OkOut, PublicUserOut
from ..schemas.calendar import (
    CompleteIn,
    CompletionOut,
    Mode,
    OccurrencesOut,
    TaskIn,
    TaskOut,
    TaskUpdateIn,
)
from ..services import calendar as svc
from ..services import users as users_svc
from ..services.calendar import CalendarError

router = APIRouter(prefix="/calendar", tags=["calendar"])
UK = ZoneInfo("Europe/London")


def _err(exc: CalendarError) -> HTTPException:
    return HTTPException(exc.status, exc.message)


def _task(db, task_id: int) -> Task:
    try:
        return svc.get_task(db, task_id)
    except CalendarError as exc:
        raise _err(exc) from exc


def task_out(db, task: Task, user: User) -> TaskOut:
    return TaskOut(
        id=task.id,
        title=task.title,
        description=task.description,
        category=task.category,
        category_label=CATEGORY_LABELS.get(task.category, "Other"),
        all_day=task.all_day,
        start_at=task.start_at,
        end_at=task.end_at,
        tz=task.tz,
        rrule=task.rrule,
        recurring=task.recurring,
        owner=PublicUserOut.model_validate(db.get(User, task.owner_id)),
        can_edit=user.is_admin or task.owner_id == user.id,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _csv_ints(value: str | None) -> list[int] | None:
    if not value:
        return None
    try:
        return [int(v) for v in value.split(",") if v.strip()]
    except ValueError as exc:
        raise HTTPException(422, "owners must be a comma-separated list of user ids.") from exc


@router.get("/occurrences", response_model=OccurrencesOut, response_model_by_alias=True)
def list_occurrences(
    user: CurrentUser,
    db: Db,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    owners: str | None = None,
) -> dict:
    """Occurrences between two UK dates (both inclusive; at most 62 days). Default: this week from today."""
    today = datetime.now(UTC).astimezone(UK).date()
    start_d = from_ or today
    end_d = to or start_d + timedelta(days=6)
    if end_d < start_d:
        start_d, end_d = end_d, start_d
    lo = datetime.combine(start_d, time(0), tzinfo=UK).astimezone(UTC)
    hi = datetime.combine(end_d + timedelta(days=1), time(0), tzinfo=UK).astimezone(UTC)
    try:
        occurrences = svc.expand(db, lo, hi, _csv_ints(owners), viewer=user)
    except CalendarError as exc:
        raise _err(exc) from exc
    return {
        "occurrences": occurrences,
        "from": start_d.isoformat(),
        "to": end_d.isoformat(),
        "owners": [PublicUserOut.model_validate(u) for u in users_svc.list_users(db)],
    }


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(user: CurrentUser, db: Db, scope: ScopeParam = "everyone") -> list[TaskOut]:
    stmt = apply_scope(svc.live_tasks(db), Task.owner_id, scope, user)
    return [task_out(db, t, user) for t in db.scalars(stmt)]


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskIn, user: CurrentUser, db: Db) -> TaskOut:
    try:
        task = svc.create(db, user, **body.model_dump())
    except CalendarError as exc:
        raise _err(exc) from exc
    return task_out(db, task, user)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, user: CurrentUser, db: Db) -> TaskOut:
    return task_out(db, _task(db, task_id), user)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, body: TaskUpdateIn, user: CurrentUser, db: Db) -> TaskOut:
    task = _task(db, task_id)
    fields = body.model_dump(exclude_unset=True)
    mode = fields.pop("mode", "series")
    occurrence_date = fields.pop("occurrence_date", None)
    try:
        svc.update(db, user, task, mode=mode, occurrence_date=occurrence_date, **fields)
    except CalendarError as exc:
        raise _err(exc) from exc
    return task_out(db, task, user)


@router.delete("/tasks/{task_id}", response_model=OkOut)
def delete_task(
    task_id: int,
    user: CurrentUser,
    db: Db,
    mode: Mode = "series",
    occurrence_date: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
) -> OkOut:
    task = _task(db, task_id)
    try:
        svc.delete(db, user, task, mode=mode, occurrence_date=occurrence_date)
    except CalendarError as exc:
        raise _err(exc) from exc
    if task.rrule and mode == "occurrence":
        return OkOut(message="That occurrence was removed. The rest of the series stays.")
    return OkOut(message="Task deleted.")


def _completion_out(db, task: Task, occurrence_date: str) -> CompletionOut:
    row = db.scalar(
        select(TaskCompletion).where(
            TaskCompletion.task_id == task.id, TaskCompletion.occurrence_date == occurrence_date
        )
    )
    return CompletionOut(
        task_id=task.id,
        occurrence_date=occurrence_date,
        done=row is not None,
        completed_by=PublicUserOut.model_validate(db.get(User, row.completed_by_id)) if row else None,
        completed_at=row.completed_at if row else None,
    )


@router.post("/tasks/{task_id}/complete", response_model=CompletionOut)
def complete_task(task_id: int, body: CompleteIn, user: CurrentUser, db: Db) -> CompletionOut:
    task = _task(db, task_id)
    try:
        svc.complete(db, user, task, body.occurrence_date)
    except CalendarError as exc:
        raise _err(exc) from exc
    return _completion_out(db, task, body.occurrence_date)


@router.delete("/tasks/{task_id}/complete", response_model=CompletionOut)
def uncomplete_task(
    task_id: int,
    user: CurrentUser,
    db: Db,
    occurrence_date: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")],
) -> CompletionOut:
    task = _task(db, task_id)
    try:
        svc.uncomplete(db, user, task, occurrence_date)
    except CalendarError as exc:
        raise _err(exc) from exc
    return _completion_out(db, task, occurrence_date)
