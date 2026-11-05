"""Replay Journal: instruments, strategies, journal sessions, trades, trade_tags, screenshots.

Revision ID: 0004
Revises: 0003
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

# (symbol, name, asset_class, pip_size, unit, price_decimals, aliases)
SEED_INSTRUMENTS: list[tuple[str, str, str, float, str, int, list[str]]] = [
    ("EURUSD", "Euro / US dollar", "fx", 0.0001, "pips", 5, ["EUR/USD"]),
    ("GBPUSD", "British pound / US dollar", "fx", 0.0001, "pips", 5, ["GBP/USD"]),
    ("USDJPY", "US dollar / Japanese yen", "fx", 0.01, "pips", 3, ["USD/JPY"]),
    ("USDCHF", "US dollar / Swiss franc", "fx", 0.0001, "pips", 5, ["USD/CHF"]),
    ("AUDUSD", "Australian dollar / US dollar", "fx", 0.0001, "pips", 5, ["AUD/USD"]),
    ("USDCAD", "US dollar / Canadian dollar", "fx", 0.0001, "pips", 5, ["USD/CAD"]),
    ("NZDUSD", "New Zealand dollar / US dollar", "fx", 0.0001, "pips", 5, ["NZD/USD"]),
    ("XAUUSD", "Gold", "metal", 0.1, "points", 2, ["GOLD", "XAU/USD"]),
    ("BTCUSD", "Bitcoin", "crypto", 1.0, "points", 1, ["BTC/USD", "BTCUSDT"]),
    ("GER40", "Germany 40", "index", 1.0, "points", 1, ["DE40", "DAX", "DE40EUR", "GER40EUR", "DAX40"]),
    ("NAS100", "Nasdaq 100", "index", 1.0, "points", 1, ["NAS100USD", "US100", "USTEC", "NDX", "NQ"]),
]


def _owned() -> list[sa.Column]:
    return [
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(24), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("asset_class", sa.String(16), nullable=False, server_default="fx"),
        sa.Column("pip_size", sa.Float, nullable=False),
        sa.Column("unit", sa.String(8), nullable=False, server_default="pips"),
        sa.Column("price_decimals", sa.Integer, nullable=False, server_default="5"),
        sa.Column("aliases", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("instruments", sa.JSON, nullable=False),
        sa.Column("timeframes", sa.JSON, nullable=False),
        sa.Column("entry_models", sa.JSON, nullable=False),
        sa.Column("csv_timezone", sa.String(48), nullable=False, server_default="Europe/London"),
        sa.Column("rules", sa.JSON, nullable=False),
        sa.Column("reasoning_template", sa.JSON, nullable=False),
        sa.Column("backtest_opened_early", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("profile_cache", sa.JSON, nullable=True),
        sa.Column("profile_fingerprint", sa.String(64), nullable=True),
        *_owned(),
    )
    op.create_index("ix_strategies_owner_id", "strategies", ["owner_id"])

    op.create_table(
        "journal_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("strategy_id", sa.Integer, sa.ForeignKey("strategies.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("csv_timezone", sa.String(48), nullable=False),
        sa.Column("range_start", sa.Date, nullable=True),
        sa.Column("range_end", sa.Date, nullable=True),
        sa.Column("trade_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source_filename", sa.String(255), nullable=True),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("improve_note", sa.Text, nullable=False, server_default=""),
        sa.Column("import_report", sa.JSON, nullable=True),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        *_owned(),
    )
    op.create_index("ix_journal_sessions_strategy_id", "journal_sessions", ["strategy_id"])
    op.create_index("ix_journal_sessions_owner_id", "journal_sessions", ["owner_id"])

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("strategy_id", sa.Integer, sa.ForeignKey("strategies.id"), nullable=False),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("journal_sessions.id"), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("fx_id", sa.String(32), nullable=True),
        sa.Column("instrument", sa.String(24), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("market_date", sa.Date, nullable=False),
        sa.Column("session_label", sa.String(16), nullable=False, server_default=""),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("entry_price", sa.Float, nullable=True),
        sa.Column("initial_sl", sa.Float, nullable=True),
        sa.Column("max_tp", sa.Float, nullable=True),
        sa.Column("ideal_tp", sa.Float, nullable=True),
        sa.Column("exit_price", sa.Float, nullable=True),
        sa.Column("sl_distance", sa.Float, nullable=True),
        sa.Column("tp_distance", sa.Float, nullable=True),
        sa.Column("tp_r", sa.Float, nullable=True),
        sa.Column("r_multiple", sa.Float, nullable=True),
        sa.Column("pnl", sa.Float, nullable=True),
        sa.Column("outcome", sa.String(10), nullable=True),
        sa.Column("entry_model", sa.String(80), nullable=True),
        sa.Column("reasoning", sa.JSON, nullable=False),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("rules_followed", sa.JSON, nullable=False),
        sa.Column("mae_r", sa.Float, nullable=True),
        sa.Column("mfe_r", sa.Float, nullable=True),
        sa.Column("news_impact", sa.String(8), nullable=True),
        sa.Column("news_events", sa.JSON, nullable=True),
        sa.Column("raw_row", sa.JSON, nullable=True),
        *_owned(),
        sa.UniqueConstraint("strategy_id", "fx_id", name="uq_trades_strategy_fx_id"),
    )
    for col in ("strategy_id", "session_id", "owner_id", "opened_at", "market_date"):
        op.create_index(f"ix_trades_{col}", "trades", [col])

    op.create_table(
        "trade_tags",
        sa.Column("trade_id", sa.Integer, sa.ForeignKey("trades.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer, sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "screenshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("trade_id", sa.Integer, sa.ForeignKey("trades.id"), nullable=False),
        sa.Column("slot", sa.String(8), nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("full_key", sa.String(255), nullable=False),
        sa.Column("thumb_key", sa.String(255), nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("bytes", sa.Integer, nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        *_owned(),
    )
    op.create_index("ix_screenshots_trade_id", "screenshots", ["trade_id"])
    op.create_index("ix_screenshots_owner_id", "screenshots", ["owner_id"])

    instruments = sa.table(
        "instruments",
        sa.column("symbol", sa.String),
        sa.column("name", sa.String),
        sa.column("asset_class", sa.String),
        sa.column("pip_size", sa.Float),
        sa.column("unit", sa.String),
        sa.column("price_decimals", sa.Integer),
        sa.column("aliases", sa.JSON),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        instruments,
        [
            {
                "symbol": sym,
                "name": name,
                "asset_class": cls,
                "pip_size": pip,
                "unit": unit,
                "price_decimals": dec,
                "aliases": aliases,
                "created_at": now,
                "updated_at": now,
            }
            for sym, name, cls, pip, unit, dec, aliases in SEED_INSTRUMENTS
        ],
    )


def downgrade() -> None:
    for table in ("screenshots", "trade_tags", "trades", "journal_sessions", "strategies", "instruments"):
        op.drop_table(table)
