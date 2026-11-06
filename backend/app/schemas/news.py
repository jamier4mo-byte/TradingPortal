"""News Room request and response shapes (docs/build/prompt4-api.md). Times are ISO UTC strings."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..services.market_prefs import MAX_WINDOW_MINUTES, MIN_WINDOW_MINUTES

Impact = Literal["high", "medium", "low", "holiday", "none"]


class SurpriseOut(BaseModel):
    direction: Literal["up", "down", "inline"]
    diff: float
    diff_text: str
    better: bool | None
    wording: str


class EventOut(BaseModel):
    id: int
    title: str
    name: str
    currency: str
    at: str
    uk_date: str
    uk_time: str
    all_day: bool
    impact: str
    impact_label: str
    forecast: str | None
    previous: str | None
    actual: str | None
    revised: str | None
    released: bool
    surprise: SurpriseOut | None
    instruments: list[str]
    mine: bool
    event_type_id: int | None
    has_explanation: bool


class FeedStatusOut(BaseModel):
    feed: str
    last_success_at: str | None
    last_attempt_at: str | None
    last_status: str | None
    last_error: str | None


class CoverageRangeOut(BaseModel):
    source: str
    start_date: str
    end_date: str


class JBlankedStatusOut(BaseModel):
    configured: bool
    requests_today: int
    daily_budget: int
    next_slot_at: str | None


class StatusOut(BaseModel):
    last_updated_at: str | None
    feeds: list[FeedStatusOut]
    coverage: list[CoverageRangeOut]
    jblanked: JBlankedStatusOut


class EventsOut(BaseModel):
    model_config = {"populate_by_name": True}

    events: list[EventOut]
    from_: str = Field(alias="from", serialization_alias="from")
    to: str
    last_updated_at: str | None
    window_minutes: int
    my_instruments: list[str]


class EventTypeOut(BaseModel):
    id: int
    name: str
    category: str
    explanation: str | None
    why_it_matters: str | None
    higher_is_better: bool | None


class HistoryRowOut(BaseModel):
    event_id: int
    at: str
    actual: str | None
    forecast: str | None
    previous: str | None
    surprise: SurpriseOut | None


class HorizonOut(BaseModel):
    status: str
    range: float | None
    move: float | None
    direction: str | None


class ReactionRowOut(BaseModel):
    event_id: int
    at: str
    horizons: dict[str, HorizonOut]


class ReactionsOut(BaseModel):
    instrument: str
    unit: str
    releases: int
    average_range: dict[str, float | None]
    rows: list[ReactionRowOut]


class EmptyTextOut(BaseModel):
    history: str | None
    reactions: str | None


class EventDetailOut(BaseModel):
    event: EventOut
    type: EventTypeOut | None
    history: list[HistoryRowOut]
    reactions: list[ReactionsOut]
    summary: str | None
    empty: EmptyTextOut


class TodayOut(BaseModel):
    headline: str
    high_count: int
    events: list[EventOut]
    last_updated_at: str | None


class NextOut(BaseModel):
    event: EventOut | None
    seconds_until: int | None
    server_now: str


class WeekDayOut(BaseModel):
    date: str
    label: str
    events: list[EventOut]


class WeekAheadOut(BaseModel):
    start: str
    end: str
    default_view: bool
    days: list[WeekDayOut]


class SessionSpanOut(BaseModel):
    name: Literal["Asia", "London", "New York"]
    start: str
    end: str


class WindowOut(BaseModel):
    event_id: int
    start: str
    end: str


class TimelineOut(BaseModel):
    date: str
    window_minutes: int
    sessions: list[SessionSpanOut]
    events: list[EventOut]
    windows: list[WindowOut]


class InstrumentChoiceOut(BaseModel):
    code: str
    name: str


class PrefsOut(BaseModel):
    instruments: list[str]
    news_window_minutes: int
    available: list[InstrumentChoiceOut]


class PrefsIn(BaseModel):
    instruments: list[str] | None = Field(default=None, max_length=50)
    news_window_minutes: int | None = Field(default=None, ge=MIN_WINDOW_MINUTES, le=MAX_WINDOW_MINUTES)

    @field_validator("instruments")
    @classmethod
    def _upper(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out: list[str] = []
        for code in v:
            code = code.strip().upper()
            if code and code not in out:
                out.append(code)
        return out


class InstrumentMapRow(BaseModel):
    currency: str = Field(min_length=2, max_length=8)
    instrument: str = Field(min_length=2, max_length=24)

    @field_validator("currency", "instrument")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class BriefNewsOut(BaseModel):
    month: str
    status: Literal["ok", "partial", "no_data"]
    high_count: int
    events: list[EventOut]
    note: str
