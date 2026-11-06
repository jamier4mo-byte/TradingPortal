"""Replay Journal: instruments, strategies, import sessions, trades, screenshots.

Every owned record carries owner_id, created_at, updated_at and deleted_at (OwnedRecordMixin).
Times are stored in UTC; the CSV's naive clock times are converted on import using the
strategy's csv_timezone. Market date and session label are derived in UK time (Europe/London).
"""

from datetime import date, datetime
from typing import Literal

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, OwnedRecordMixin, TimestampMixin, UTCDateTime
from .tag import Tag

SessionKind = Literal["ideal", "backtest", "manual"]
TradeKind = Literal["ideal", "backtest", "missed"]
Outcome = Literal["win", "loss", "breakeven"]
Slot = Literal["entry", "exit", "extra"]

SLOTS = ("entry", "exit", "extra")
MAX_EXTRA_SCREENSHOTS = 3

DEFAULT_REASONING_TEMPLATE: list[dict] = [
    {"key": "htf_bias", "label": "HTF bias"},
    {"key": "draw_on_liquidity", "label": "Draw on liquidity"},
    {"key": "pd_array", "label": "PD array / entry model"},
    {"key": "killzone", "label": "Killzone"},
    {"key": "confluences", "label": "Confluences"},
    {"key": "invalidation", "label": "Invalidation"},
]

DEFAULT_RULES: list[dict] = [
    {"key": "r1", "text": "HTF bias agrees with the trade direction"},
    {"key": "r2", "text": "Entry taken inside the killzone"},
    {"key": "r3", "text": "Stop placed beyond the invalidation level"},
    {"key": "r4", "text": "Target is a real draw on liquidity"},
]


class Instrument(TimestampMixin, Base):
    """Pip or point size per instrument. Seeded; the admin edits."""

    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    asset_class: Mapped[str] = mapped_column(
        String(16), nullable=False, default="fx"
    )  # fx|metal|crypto|index
    pip_size: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False, default="pips")  # pips|points
    price_decimals: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)  # FX Replay spellings


class Strategy(OwnedRecordMixin, Base):
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    instruments: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    timeframes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    entry_models: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    csv_timezone: Mapped[str] = mapped_column(String(48), nullable=False, default="Europe/London")
    rules: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)  # [{key, text}] 4–8
    reasoning_template: Mapped[list[dict]] = mapped_column(
        JSON, nullable=False, default=list
    )  # [{key, label}]
    backtest_opened_early: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    profile_cache: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    profile_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)

    trades: Mapped[list["Trade"]] = relationship(back_populates="strategy")
    sessions: Mapped[list["JournalSession"]] = relationship(back_populates="strategy")


class JournalSession(OwnedRecordMixin, Base):
    """One FX Replay session: an upload (or a run of manual logging) that produced trades (U1).

    Called journal_sessions because `sessions` is the sign-in table.
    """

    __tablename__ = "journal_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # ideal | backtest | manual
    csv_timezone: Mapped[str] = mapped_column(String(48), nullable=False)
    range_start: Mapped[date | None] = mapped_column(Date, nullable=True)  # replayed dates (UK)
    range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    improve_note: Mapped[str] = mapped_column(Text, nullable=False, default="")  # "one thing to improve"
    import_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    undone_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    strategy: Mapped[Strategy] = relationship(back_populates="sessions")
    trades: Mapped[list["Trade"]] = relationship(back_populates="session")


trade_tags = Table(
    "trade_tags",
    Base.metadata,
    Column("trade_id", ForeignKey("trades.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Trade(OwnedRecordMixin, Base):
    __tablename__ = "trades"
    __table_args__ = (UniqueConstraint("strategy_id", "kind", "fx_id", name="uq_trades_strategy_kind_fx_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategies.id"), nullable=False, index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_sessions.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # ideal | backtest | missed
    fx_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # FX Replay trade id
    instrument: Mapped[str] = mapped_column(String(24), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # buy | sell

    opened_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    market_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)  # UK date of the open
    session_label: Mapped[str] = mapped_column(String(16), nullable=False, default="")  # Asia|London|New York
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    initial_sl: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    ideal_tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sl_distance: Mapped[float | None] = mapped_column(Float, nullable=True)  # pips or points
    tp_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp_r: Mapped[float | None] = mapped_column(Float, nullable=True)  # TP distance as R
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)  # realised R
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(10), nullable=True)  # win | loss | breakeven

    entry_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reasoning: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # keyed by template field
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rules_followed: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )  # keyed by rule key → bool
    mae_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    mfe_r: Mapped[float | None] = mapped_column(Float, nullable=True)

    # News fields: filled by Prompt 4
    news_impact: Mapped[str | None] = mapped_column(String(8), nullable=True)
    news_events: Mapped[list | None] = mapped_column(JSON, nullable=True)

    raw_row: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    strategy: Mapped[Strategy] = relationship(back_populates="trades")
    session: Mapped[JournalSession | None] = relationship(back_populates="trades")
    tags: Mapped[list[Tag]] = relationship(secondary=trade_tags, lazy="selectin")
    screenshots: Mapped[list["Screenshot"]] = relationship(back_populates="trade", lazy="selectin")


class Screenshot(OwnedRecordMixin, Base):
    __tablename__ = "screenshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"), nullable=False, index=True)
    slot: Mapped[str] = mapped_column(String(8), nullable=False)  # entry | exit | extra
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    full_key: Mapped[str] = mapped_column(String(255), nullable=False)
    thumb_key: Mapped[str] = mapped_column(String(255), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    trade: Mapped[Trade] = relationship(back_populates="screenshots")
