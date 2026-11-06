from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .auth import PublicUserOut
from .tags import TagOut

Kind = Literal["ideal", "backtest", "missed"]
SessionKind = Literal["ideal", "backtest", "manual"]
Side = Literal["buy", "sell"]
Slot = Literal["htf", "entry", "outcome", "extra"]
Stage = Literal["ideal", "ready", "backtesting"]


class RuleIn(BaseModel):
    key: str | None = None
    text: str = Field(max_length=200)


class TemplateFieldIn(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=80)


class InstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    name: str
    asset_class: str
    pip_size: float
    unit: str
    price_decimals: int
    aliases: list[str]


class InstrumentIn(BaseModel):
    symbol: str = Field(min_length=2, max_length=24)
    name: str = Field(min_length=1, max_length=80)
    asset_class: Literal["fx", "metal", "crypto", "index", "other"] = "fx"
    pip_size: float = Field(gt=0)
    unit: Literal["pips", "points"] = "pips"
    price_decimals: int = Field(ge=0, le=8, default=5)
    aliases: list[str] = Field(default_factory=list, max_length=20)


class InstrumentUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    asset_class: Literal["fx", "metal", "crypto", "index", "other"] | None = None
    pip_size: float | None = Field(default=None, gt=0)
    unit: Literal["pips", "points"] | None = None
    price_decimals: int | None = Field(default=None, ge=0, le=8)
    aliases: list[str] | None = Field(default=None, max_length=20)


class CoverageOut(BaseModel):
    months: list[dict]
    covered_count: int
    best_run: int
    current_run: int
    trade_count: int
    unlocked: bool
    first_month: str | None
    last_month: str | None
    next_uncovered: str | None
    progress: float
    target_months: int
    min_trades: int


class StatsOut(BaseModel):
    trades: int
    win_rate: float | None
    total_r: float | None
    avg_r: float | None
    total_pnl: float | None
    rules_followed_rate: float | None


class StrategyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    instruments: list[str] = Field(default_factory=list, max_length=20)
    timeframes: list[str] = Field(default_factory=list, max_length=12)
    entry_models: list[str] = Field(default_factory=list, max_length=20)
    csv_timezone: Literal["Europe/London", "UTC"] = "Europe/London"
    rules: list[RuleIn] | None = None
    reasoning_template: list[TemplateFieldIn] | None = None


class StrategyUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    instruments: list[str] | None = Field(default=None, max_length=20)
    timeframes: list[str] | None = Field(default=None, max_length=12)
    entry_models: list[str] | None = Field(default=None, max_length=20)
    csv_timezone: Literal["Europe/London", "UTC"] | None = None
    rules: list[RuleIn] | None = None
    reasoning_template: list[TemplateFieldIn] | None = None
    backtest_opened_early: bool | None = None


class StrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    instruments: list[str]
    timeframes: list[str]
    entry_models: list[str]
    csv_timezone: str
    rules: list[dict]
    reasoning_template: list[dict]
    backtest_opened_early: bool
    owner_id: int
    owner: PublicUserOut
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    # computed
    stage: Stage
    ideal_count: int
    backtest_count: int
    missed_count: int
    range_start: date | None
    range_end: date | None
    coverage: CoverageOut
    backtest_stats: StatsOut | None
    sparkline: list[float]
    last_trade_at: datetime | None
    can_edit: bool


class ScreenshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trade_id: int
    slot: Slot
    position: int
    width: int
    height: int
    bytes: int
    content_type: str
    captured_at: datetime | None
    original_filename: str | None
    created_at: datetime
    full_url: str
    thumb_url: str


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_id: int
    session_id: int | None
    owner_id: int
    owner: PublicUserOut
    kind: Kind
    fx_id: str | None
    instrument: str
    side: Side
    opened_at: datetime
    closed_at: datetime | None
    market_date: date
    session_label: str
    duration_seconds: int | None
    entry_price: float | None
    initial_sl: float | None
    max_tp: float | None
    ideal_tp: float | None
    exit_price: float | None
    sl_distance: float | None
    tp_distance: float | None
    tp_r: float | None
    r_multiple: float | None
    pnl: float | None
    outcome: Literal["win", "loss", "breakeven"] | None
    entry_model: str | None
    reasoning: dict[str, Any]
    notes: str
    rules_followed: dict[str, Any]
    mae_r: float | None
    mfe_r: float | None
    news_impact: str | None
    annotated_at: datetime | None
    tags: list[TagOut]
    screenshots: list[ScreenshotOut]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    can_edit: bool


class TradeIn(BaseModel):
    kind: Kind = "ideal"
    instrument: str = Field(min_length=2, max_length=32)
    side: Side
    opened_at: datetime
    closed_at: datetime | None = None
    entry_price: float | None = None
    initial_sl: float | None = None
    max_tp: float | None = None
    ideal_tp: float | None = None
    exit_price: float | None = None
    r_multiple: float | None = None
    pnl: float | None = None
    entry_model: str | None = Field(default=None, max_length=80)
    reasoning: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=8000)
    rules_followed: dict[str, Any] | None = None
    mae_r: float | None = None
    mfe_r: float | None = None
    tags: list[str] | None = Field(default=None, max_length=30)
    session_id: int | None = None


class TradeUpdateIn(BaseModel):
    instrument: str | None = Field(default=None, min_length=2, max_length=32)
    side: Side | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    entry_price: float | None = None
    initial_sl: float | None = None
    max_tp: float | None = None
    exit_price: float | None = None
    r_multiple: float | None = None
    pnl: float | None = None
    entry_model: str | None = Field(default=None, max_length=80)
    reasoning: dict[str, Any] | None = None
    notes: str | None = Field(default=None, max_length=8000)
    rules_followed: dict[str, Any] | None = None
    mae_r: float | None = None
    mfe_r: float | None = None
    tags: list[str] | None = Field(default=None, max_length=30)
    annotated: bool | None = None  # mark the trade completed (or not) by hand


class SessionProgressOut(BaseModel):
    trades: int
    screenshots: int
    screenshots_target: int
    reasons: int
    reasons_target: int
    completed: int


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_id: int
    owner_id: int
    owner: PublicUserOut
    kind: SessionKind
    csv_timezone: str
    range_start: date | None
    range_end: date | None
    trade_count: int
    source_filename: str | None
    improve_note: str
    import_report: dict | None
    undone_at: datetime | None
    created_at: datetime
    deleted_at: datetime | None
    progress: SessionProgressOut
    stats: StatsOut
    can_edit: bool


class SessionUpdateIn(BaseModel):
    improve_note: str | None = Field(default=None, max_length=2000)


class PreviewRowOut(BaseModel):
    fx_id: str
    line: int
    instrument: str
    side: Side
    opened_at: datetime
    closed_at: datetime | None
    opened_uk: str
    pnl: float
    r_multiple: float | None
    outcome: Literal["win", "loss", "breakeven"] | None
    duplicate: dict[str, bool]  # per destination
    tags: list[str]


class ImportPreviewOut(BaseModel):
    filename: str
    file_hash: str
    timezone: str
    rows_parsed: int
    rows_total: int
    problems: list[str]
    unknown_columns: list[str]
    range_start: date | None
    range_end: date | None
    winners: int
    losers: int
    breakevens: int
    duplicates: dict[str, int]  # per destination
    would_import: dict[str, int]
    breakeven_threshold: float
    rows: list[PreviewRowOut]


class ImportResultOut(BaseModel):
    session: SessionOut
    report: dict
    trades: list[TradeOut]


class UndoOut(BaseModel):
    ok: bool = True
    trades: int
    session_id: int


class MatchFileIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    captured_at: datetime | None = None
    time_source: Literal["exif", "name", "mtime", "none"] = "mtime"


class MatchIn(BaseModel):
    files: list[MatchFileIn] = Field(max_length=200)


class MatchOut(BaseModel):
    file: str
    trade_id: int | None
    slot: Slot | None
    confidence: Literal["high", "medium", "low", "none"]
    reason: str


class ScreenshotMoveIn(BaseModel):
    trade_id: int
    slot: Slot


class TrashOut(BaseModel):
    days: int
    strategies: list[StrategyOut]
    sessions: list[SessionOut]
    trades: list[TradeOut]


class SummaryOut(BaseModel):
    strategies: int
    trades: int
    unlocked: int
    last_session: SessionOut | None
    my_last_session: SessionOut | None


class BriefOut(BaseModel):
    strategy: StrategyOut
    profile: dict | None
    rules: list[dict]
    recent_improve_notes: list[dict]
    next_uncovered: str | None
    news: None = None  # Prompt 4 fills this slot
