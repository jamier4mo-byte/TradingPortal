"""News Room: event types, events from both feeds, history coverage, feed runs, instrument mapping.

Times are UTC. Shown in UK time (Europe/London) by the front end and the services.
Two free sources (Foundations 3.7): the Forex Factory weekly JSON (schedule, impact, forecast,
previous) and the JBlanked News API (actuals and history). Both upsert into `events`.
"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UTCDateTime, utcnow

IMPACTS = ("high", "medium", "low", "holiday", "none")


class EventType(TimestampMixin, Base):
    """One kind of release, e.g. "US Non-Farm Payrolls". Seeded with plain-English explanations;
    unknown titles from a feed create an unseeded row with no explanation yet."""

    __tablename__ = "event_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)  # "USD:nfp"
    name: Mapped[str] = mapped_column(String(120), nullable=False)  # canonical display name
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    # True: a higher actual is better for the currency; False: lower is better (e.g. unemployment);
    # None: no better/worse wording (speeches, decisions without a number).
    higher_is_better: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_it_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)  # feed titles
    jb_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    events: Mapped[list["Event"]] = relationship(back_populates="event_type")


class Event(TimestampMixin, Base):
    """One scheduled release. Forex Factory and JBlanked rows for the same release are merged."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_currency_at", "currency", "at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type_id: Mapped[int | None] = mapped_column(ForeignKey("event_types.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)  # as the feed wrote it
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    impact: Mapped[str] = mapped_column(String(8), nullable=False, default="low")  # IMPACTS
    # Figures exactly as published ("0.3%", "185K") plus a parsed number for surprise maths.
    forecast: Mapped[str | None] = mapped_column(String(32), nullable=True)
    previous: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actual: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revised: Mapped[str | None] = mapped_column(String(32), nullable=True)
    forecast_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)  # first seen
    # Source ids: Forex Factory has none, so ff_key is a stable hash of currency + title + UK date.
    ff_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    jb_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    jb_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sources: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)

    event_type: Mapped[EventType | None] = relationship(back_populates="events")


class NewsHistoryCoverage(Base):
    """Date ranges (UK dates, inclusive) where we hold real event history. Outside them a trade
    gets "No news data" rather than a guess (F4)."""

    __tablename__ = "news_history_coverage"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(24), nullable=False)  # forex_factory | jblanked
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)


class FeedRun(Base):
    """Every fetch attempt, so failures are logged and "last updated" is visible."""

    __tablename__ = "feed_runs"
    __table_args__ = (Index("ix_feed_runs_feed_started", "feed", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    feed: Mapped[str] = mapped_column(String(24), nullable=False)  # forex_factory | jblanked | backfill
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="running")  # ok | error | skipped
    made_request: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    events_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_changed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class NewsInstrumentMap(Base):
    """Which instruments an event currency moves (3.1 + F19). One editable table, seeded."""

    __tablename__ = "news_instrument_map"
    __table_args__ = (UniqueConstraint("currency", "instrument", name="uq_news_instrument_map"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    instrument: Mapped[str] = mapped_column(String(24), nullable=False)  # instruments.symbol, e.g. XAUUSD


class UserMarketPrefs(Base):
    """Per-user News Room and price preferences. A missing row means the defaults."""

    __tablename__ = "user_market_prefs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    instruments: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)  # followed codes
    news_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    allow_background_jobs: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    background_daily_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=150)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow)


class Lease(Base):
    """A named lease or rate slot shared by every process through the database.

    Scheduler: the holder renews it each tick; another process takes over once it expires.
    JBlanked: `expires_at` is the next moment a request is allowed (one per interval, globally).
    """

    __tablename__ = "leases"

    name: Mapped[str] = mapped_column(String(48), primary_key=True)
    holder: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class AppState(Base):
    """Small key → JSON store for job cursors (e.g. the resumable history backfill)."""

    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow)
