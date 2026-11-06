"""Team calendar schemas (1.4). Times are UTC ISO strings; `occurrence_date` is the original local date."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .auth import PublicUserOut

Category = Literal["backtesting", "review", "admin", "other"]
Mode = Literal["series", "occurrence"]
OccurrenceDate = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    category: Category = "other"
    all_day: bool = False
    start_at: datetime
    end_at: datetime | None = None
    tz: str = Field(default="Europe/London", max_length=48)
    rrule: str | None = Field(default=None, max_length=300)


class TaskUpdateIn(BaseModel):
    """Partial update. `mode` matters only for recurring tasks; `occurrence_date` names the occurrence
    being edited (for mode=occurrence) or the one that was dragged (for a series move)."""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    category: Category | None = None
    all_day: bool | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    tz: str | None = Field(default=None, max_length=48)
    rrule: str | None = Field(default=None, max_length=300)
    mode: Mode = "series"
    occurrence_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    category: Category
    category_label: str
    all_day: bool
    start_at: datetime
    end_at: datetime | None
    tz: str
    rrule: str | None
    recurring: bool
    owner: PublicUserOut
    can_edit: bool
    created_at: datetime
    updated_at: datetime


class OccurrenceOut(BaseModel):
    id: str
    task_id: int
    occurrence_date: str
    start_at: datetime
    end_at: datetime | None
    all_day: bool
    title: str
    description: str | None
    category: Category
    category_label: str
    tz: str
    owner: PublicUserOut
    done: bool
    completed_by: PublicUserOut | None
    completed_at: datetime | None
    recurring: bool
    exception: bool
    can_edit: bool


class OccurrencesOut(BaseModel):
    occurrences: list[OccurrenceOut]
    from_: str = Field(alias="from")
    to: str
    owners: list[PublicUserOut]

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class CompleteIn(BaseModel):
    occurrence_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class CompletionOut(BaseModel):
    task_id: int
    occurrence_date: str
    done: bool
    completed_by: PublicUserOut | None
    completed_at: datetime | None
