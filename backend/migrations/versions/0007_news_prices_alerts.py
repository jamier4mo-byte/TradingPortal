"""News Room, prices and push alerts (Prompt 4).

Tables: event_types, events, news_history_coverage, feed_runs, news_instrument_map, user_market_prefs,
leases, app_state, price_symbols, price_pins, price_cache, price_credit_usage, price_reactions,
push_subscriptions, alert_prefs, alert_deliveries.

Seeds the instrument mapping (3.1 + F19) and the price symbol aliases. Event types and their
explanations are seeded by 0008.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

# Event currency → instruments it moves (Foundations 3.1, F19 adds NAS100). Editable table.
SEED_INSTRUMENT_MAP: list[tuple[str, str]] = [
    ("USD", "XAUUSD"),
    ("USD", "BTCUSD"),
    ("USD", "EURUSD"),
    ("USD", "NAS100"),
    ("EUR", "EURUSD"),
    ("EUR", "GER40"),
    ("DE", "GER40"),
    ("GBP", "GBPUSD"),
    ("JPY", "USDJPY"),
    ("AUD", "AUDUSD"),
    ("CAD", "USDCAD"),
    ("CHF", "USDCHF"),
    ("NZD", "NZDUSD"),
]

# (code, provider symbol, name, asset class, unit, pip size). Index symbols are unconfirmed on the
# free plan (F1): availability stays unknown until a real request answers.
SEED_PRICE_SYMBOLS: list[tuple[str, str, str, str, str, float]] = [
    ("EURUSD", "EUR/USD", "Euro / US dollar", "fx", "pips", 0.0001),
    ("GBPUSD", "GBP/USD", "British pound / US dollar", "fx", "pips", 0.0001),
    ("USDJPY", "USD/JPY", "US dollar / Japanese yen", "fx", "pips", 0.01),
    ("USDCHF", "USD/CHF", "US dollar / Swiss franc", "fx", "pips", 0.0001),
    ("AUDUSD", "AUD/USD", "Australian dollar / US dollar", "fx", "pips", 0.0001),
    ("USDCAD", "USD/CAD", "US dollar / Canadian dollar", "fx", "pips", 0.0001),
    ("NZDUSD", "NZD/USD", "New Zealand dollar / US dollar", "fx", "pips", 0.0001),
    ("XAUUSD", "XAU/USD", "Gold", "metal", "points", 0.1),
    ("BTCUSD", "BTC/USD", "Bitcoin", "crypto", "points", 1.0),
    ("GER40", "DAX", "Germany 40", "index", "points", 1.0),
    ("NAS100", "NDX", "Nasdaq 100", "index", "points", 1.0),
]


def upgrade() -> None:
    op.create_table(
        "event_types",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, index=True),
        sa.Column("category", sa.String(40), nullable=False, server_default=""),
        sa.Column("higher_is_better", sa.Boolean, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("why_it_matters", sa.Text, nullable=True),
        sa.Column("aliases", sa.JSON, nullable=False),
        sa.Column("jb_event_id", sa.Integer, nullable=True),
        sa.Column("seeded", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("event_type_id", sa.Integer, sa.ForeignKey("event_types.id"), nullable=True, index=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("at", TS, nullable=False, index=True),
        sa.Column("all_day", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("impact", sa.String(8), nullable=False, server_default="low"),
        sa.Column("forecast", sa.String(32), nullable=True),
        sa.Column("previous", sa.String(32), nullable=True),
        sa.Column("actual", sa.String(32), nullable=True),
        sa.Column("revised", sa.String(32), nullable=True),
        sa.Column("forecast_value", sa.Float, nullable=True),
        sa.Column("previous_value", sa.Float, nullable=True),
        sa.Column("actual_value", sa.Float, nullable=True),
        sa.Column("actual_at", TS, nullable=True),
        sa.Column("ff_key", sa.String(64), nullable=True, unique=True),
        sa.Column("jb_key", sa.String(64), nullable=True, unique=True),
        sa.Column("jb_event_id", sa.Integer, nullable=True),
        sa.Column("sources", sa.JSON, nullable=False),
        sa.Column("last_fetched_at", TS, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_index("ix_events_currency_at", "events", ["currency", "at"])
    op.create_table(
        "news_history_coverage",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_table(
        "feed_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("feed", sa.String(24), nullable=False),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("finished_at", TS, nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="running"),
        sa.Column("made_request", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("http_status", sa.Integer, nullable=True),
        sa.Column("events_seen", sa.Integer, nullable=False, server_default="0"),
        sa.Column("events_changed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("detail", sa.JSON, nullable=True),
    )
    op.create_index("ix_feed_runs_feed_started", "feed_runs", ["feed", "started_at"])
    op.create_table(
        "news_instrument_map",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("currency", sa.String(8), nullable=False, index=True),
        sa.Column("instrument", sa.String(24), nullable=False),
        sa.UniqueConstraint("currency", "instrument", name="uq_news_instrument_map"),
    )
    op.create_table(
        "user_market_prefs",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("instruments", sa.JSON, nullable=False),
        sa.Column("news_window_minutes", sa.Integer, nullable=False, server_default="15"),
        sa.Column("allow_background_jobs", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("background_daily_cap", sa.Integer, nullable=False, server_default="150"),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_table(
        "leases",
        sa.Column("name", sa.String(48), primary_key=True),
        sa.Column("holder", sa.String(64), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
    )
    op.create_table(
        "app_state",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.JSON, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_table(
        "price_symbols",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("provider_symbol", sa.String(32), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("asset_class", sa.String(16), nullable=False, server_default="fx"),
        sa.Column("unit", sa.String(8), nullable=False, server_default="pips"),
        sa.Column("pip_size", sa.Float, nullable=False, server_default="0.0001"),
        sa.Column("available", sa.Boolean, nullable=True),
        sa.Column("availability_note", sa.String(200), nullable=True),
        sa.Column("checked_at", TS, nullable=True),
    )
    op.create_table(
        "price_pins",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("user_id", "symbol", name="uq_price_pins_user_symbol"),
    )
    op.create_table(
        "price_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("message", sa.String(300), nullable=True),
        sa.Column("fetched_at", TS, nullable=False),
        sa.Column(
            "fetched_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.UniqueConstraint("kind", "key", name="uq_price_cache_kind_key"),
    )
    op.create_table(
        "price_credit_usage",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("credits", sa.Integer, nullable=False, server_default="0"),
        sa.Column("background_credits", sa.Integer, nullable=False, server_default="0"),
        sa.Column("requests", sa.Integer, nullable=False, server_default="0"),
        sa.Column("provider_reported", sa.Integer, nullable=True),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_table(
        "price_reactions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("instrument", sa.String(32), nullable=False),
        sa.Column("horizon_minutes", sa.Integer, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("open_price", sa.Float, nullable=True),
        sa.Column("close_price", sa.Float, nullable=True),
        sa.Column("high", sa.Float, nullable=True),
        sa.Column("low", sa.Float, nullable=True),
        sa.Column("range_units", sa.Float, nullable=True),
        sa.Column("move_units", sa.Float, nullable=True),
        sa.Column("direction", sa.String(8), nullable=True),
        sa.Column("unit", sa.String(8), nullable=False, server_default="pips"),
        sa.Column("computed_at", TS, nullable=False),
        sa.Column(
            "computed_with_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.UniqueConstraint("event_id", "instrument", "horizon_minutes", name="uq_price_reactions"),
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("endpoint", sa.Text, nullable=False, unique=True),
        sa.Column("p256dh", sa.String(200), nullable=False),
        sa.Column("auth", sa.String(100), nullable=False),
        sa.Column("device_label", sa.String(80), nullable=False, server_default="This device"),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("last_success_at", TS, nullable=True),
        sa.Column("last_error", sa.String(300), nullable=True),
    )
    op.create_table(
        "alert_prefs",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("minutes_before", sa.Integer, nullable=False, server_default="15"),
        sa.Column("currencies", sa.JSON, nullable=True),
        sa.Column("impacts", sa.JSON, nullable=False),
        sa.Column("quiet_start", sa.String(5), nullable=True),
        sa.Column("quiet_end", sa.String(5), nullable=True),
        sa.Column("chime", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("updated_at", TS, nullable=False),
    )
    op.create_table(
        "alert_deliveries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column(
            "subscription_id",
            sa.Integer,
            sa.ForeignKey("push_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="sent"),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("subscription_id", "event_id", name="uq_alert_deliveries"),
    )

    imap = sa.table(
        "news_instrument_map", sa.column("currency", sa.String), sa.column("instrument", sa.String)
    )
    op.bulk_insert(imap, [{"currency": c, "instrument": i} for c, i in SEED_INSTRUMENT_MAP])
    symbols = sa.table(
        "price_symbols",
        sa.column("code", sa.String),
        sa.column("provider_symbol", sa.String),
        sa.column("name", sa.String),
        sa.column("asset_class", sa.String),
        sa.column("unit", sa.String),
        sa.column("pip_size", sa.Float),
    )
    op.bulk_insert(
        symbols,
        [
            {"code": c, "provider_symbol": p, "name": n, "asset_class": a, "unit": u, "pip_size": s}
            for c, p, n, a, u, s in SEED_PRICE_SYMBOLS
        ],
    )


def downgrade() -> None:
    for table in (
        "alert_deliveries",
        "alert_prefs",
        "push_subscriptions",
        "price_reactions",
        "price_credit_usage",
        "price_cache",
        "price_pins",
        "price_symbols",
        "app_state",
        "leases",
        "user_market_prefs",
        "news_instrument_map",
        "feed_runs",
        "news_history_coverage",
        "events",
        "event_types",
    ):
        op.drop_table(table)
