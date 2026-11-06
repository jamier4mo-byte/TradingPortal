"""Request shapes for the analytics query and the exports (2.4). Responses are plain JSON documents."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Source = Literal["ideal", "backtest", "compare"]
Scope = Literal["mine", "everyone", "others"]


class AnalyticsFilters(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    instruments: list[str] = Field(default_factory=list, max_length=50)
    sessions: list[str] = Field(default_factory=list, max_length=10)
    time_from: str | None = Field(default=None, description="Entry-time window start, UK HH:MM")
    time_to: str | None = Field(default=None, description="Entry-time window end, UK HH:MM (wraps midnight)")
    weekdays: list[int] = Field(default_factory=list, max_length=7, description="0 = Monday")
    entry_models: list[str] = Field(default_factory=list, max_length=50)
    directions: list[Literal["buy", "sell"]] = Field(default_factory=list, max_length=2)
    tags: list[str] = Field(default_factory=list, max_length=50, description="Names or synonyms")
    outcomes: list[Literal["win", "loss", "breakeven"]] = Field(default_factory=list, max_length=3)
    owners: list[int] = Field(default_factory=list, max_length=50)
    rules: Literal["all_kept", "any_broken"] | None = None
    news: Literal["inside", "outside"] | None = None

    @field_validator("time_from", "time_to")
    @classmethod
    def _clock(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        hh, _, mm = v.partition(":")
        if not (hh.isdigit() and mm.isdigit() and 0 <= int(hh) < 24 and 0 <= int(mm) < 60):
            raise ValueError("use HH:MM")
        return f"{int(hh):02d}:{int(mm):02d}"

    @field_validator("weekdays")
    @classmethod
    def _days(cls, v: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("weekdays are 0 (Monday) to 6 (Sunday)")
        return v


class AnalyticsQuery(BaseModel):
    source: Source = "backtest"
    strategy_id: int | None = None
    scope: Scope = "everyone"
    split_by_owner: bool = False
    filters: AnalyticsFilters = Field(default_factory=AnalyticsFilters)


class ExportQuery(AnalyticsQuery):
    include_images: bool = True
