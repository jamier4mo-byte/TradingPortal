"""Prices API shapes (docs/build/prompt4-api.md, Prices)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

QuoteStatus = Literal["ok", "stale", "unavailable", "no_key", "error"]


class QuoteOut(BaseModel):
    symbol: str
    code: str | None
    name: str
    unit: str | None
    decimals: int | None
    status: QuoteStatus
    price: float | None
    change: float | None
    percent_change: float | None
    open: float | None
    high: float | None
    low: float | None
    previous_close: float | None
    is_market_open: bool | None
    market_time: datetime | None
    updated_at: datetime | None
    message: str | None


class UsageOut(BaseModel):
    provider: Literal["twelve_data", "fake"]
    has_key: bool
    used: int
    limit: int
    background_used: int
    background_cap: int
    allow_background_jobs: bool
    resets_at: datetime
    paused: bool
    paused_reason: str | None


class QuotesOut(BaseModel):
    quotes: list[QuoteOut]
    usage: UsageOut
    refresh_seconds: int


class SearchResultOut(BaseModel):
    symbol: str
    code: str | None
    name: str
    exchange: str | None
    type: str | None
    available: bool | None


class SearchOut(BaseModel):
    results: list[SearchResultOut]
    cached: bool


class PinOut(BaseModel):
    symbol: str
    code: str | None
    name: str
    position: int


class PinsOut(BaseModel):
    pins: list[PinOut]
    max: int


class PinIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)


class PinOrderIn(BaseModel):
    symbols: list[str] = Field(max_length=50)


class SparkPoint(BaseModel):
    t: datetime
    v: float


class SparklineOut(BaseModel):
    symbol: str
    code: str | None
    status: QuoteStatus
    interval: str
    points: list[SparkPoint]
    updated_at: datetime | None
    message: str | None


class PriceSettingsIn(BaseModel):
    allow_background_jobs: bool | None = None
    background_daily_cap: int | None = Field(default=None, ge=0, le=800)


class OkOut(BaseModel):
    ok: bool = True
