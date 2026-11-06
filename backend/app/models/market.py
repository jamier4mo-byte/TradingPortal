"""Prices (F1, F13) and push alerts (F7).

Prices: every request uses the user's own Twelve Data key; one shared cache keyed by symbol; credits
are charged to whoever's key fetched. Push: Web Push subscriptions per device, per-user alert
preferences, and a delivery table so each user, device and event gets one notification.
"""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UTCDateTime, utcnow


class PriceSymbol(Base):
    """Our instrument code → the provider's symbol (XAUUSD → XAU/USD), and whether the plan has it."""

    __tablename__ = "price_symbols"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)  # XAUUSD
    provider_symbol: Mapped[str] = mapped_column(String(32), nullable=False)  # XAU/USD
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(16), nullable=False, default="fx")
    unit: Mapped[str] = mapped_column(String(8), nullable=False, default="pips")  # pips | points
    pip_size: Mapped[float] = mapped_column(Float, nullable=False, default=0.0001)
    # None = not checked yet; False = "Not available on your Twelve Data plan".
    available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    availability_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class PricePin(Base):
    """A user's pinned instrument (watchlist). Capped at 8 per user."""

    __tablename__ = "price_pins"
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_price_pins_user_symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)  # code if known, else provider symbol
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)


class PriceCache(Base):
    """Shared cache keyed by (kind, key): quote 15 min, sparkline 15 min, search 24 h."""

    __tablename__ = "price_cache"
    __table_args__ = (UniqueConstraint("kind", "key", name="uq_price_cache_kind_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # quote | sparkline | search | series
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")  # ok | unavailable | error
    payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    fetched_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class PriceCreditUsage(Base):
    """Credits each user's key has spent per Twelve Data day (UTC). 800 a day on the free plan."""

    __tablename__ = "price_credit_usage"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # all, background included
    background_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_reported: Mapped[int | None] = mapped_column(Integer, nullable=True)  # from /api_usage
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow)


class PriceReaction(Base):
    """How an instrument moved in the 5, 15 and 60 minutes after a release (3.3). Computed once."""

    __tablename__ = "price_reactions"
    __table_args__ = (
        UniqueConstraint("event_id", "instrument", "horizon_minutes", name="uq_price_reactions"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument: Mapped[str] = mapped_column(String(32), nullable=False)  # our code, e.g. XAUUSD
    horizon_minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # 5 | 15 | 60
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")  # ok | unavailable | none
    open_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_units: Mapped[float | None] = mapped_column(Float, nullable=True)  # high − low in pips/points
    move_units: Mapped[float | None] = mapped_column(Float, nullable=True)  # close − open in pips/points
    direction: Mapped[str | None] = mapped_column(String(8), nullable=True)  # up | down | flat
    unit: Mapped[str] = mapped_column(String(8), nullable=False, default="pips")
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    computed_with_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class PushSubscription(Base):
    """One browser/device's Web Push subscription. Pruned when the push service answers 404/410."""

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(100), nullable=False)
    device_label: Mapped[str] = mapped_column(String(80), nullable=False, default="This device")
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)


class AlertPrefs(Base):
    """Per-user alert settings. A missing row means alerts are off."""

    __tablename__ = "alert_prefs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    minutes_before: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    currencies: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)  # None = my instruments'
    impacts: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=lambda: ["high"])
    quiet_start: Mapped[str | None] = mapped_column(String(5), nullable=True)  # UK "22:00"
    quiet_end: Mapped[str | None] = mapped_column(String(5), nullable=True)  # UK "07:00"
    chime: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow)


class AlertDelivery(Base):
    """Dedupe: one row per (device, event). Status sent | skipped_quiet | failed."""

    __tablename__ = "alert_deliveries"
    __table_args__ = (UniqueConstraint("subscription_id", "event_id", name="uq_alert_deliveries"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("push_subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="sent")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
