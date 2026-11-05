"""Seed the shared ICT/SMC tag vocabulary (U5).

Revision ID: 0003
Revises: 0002
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# (name, slug, category, synonyms)
SEED_TAGS: list[tuple[str, str, str, list[str]]] = [
    # PD arrays
    ("FVG", "fvg", "pd_array", ["fair value gap", "imbalance", "f.v.g"]),
    ("IFVG", "ifvg", "pd_array", ["inverse fair value gap", "inversion fvg", "inverted fvg"]),
    ("Order block", "order-block", "pd_array", ["OB", "bullish order block", "bearish order block"]),
    ("Breaker", "breaker", "pd_array", ["breaker block", "BB"]),
    ("Mitigation block", "mitigation-block", "pd_array", ["MB", "mitigation"]),
    ("Volume imbalance", "volume-imbalance", "pd_array", ["VI"]),
    ("NWOG", "nwog", "pd_array", ["new week opening gap"]),
    ("NDOG", "ndog", "pd_array", ["new day opening gap"]),
    ("OTE", "ote", "pd_array", ["optimal trade entry", "62-79 retracement"]),
    ("Premium", "premium", "pd_array", ["premium array", "premium zone"]),
    ("Discount", "discount", "pd_array", ["discount array", "discount zone"]),
    ("PD array", "pd-array", "pd_array", ["premium discount array", "pda"]),
    # Structure
    ("BOS", "bos", "structure", ["break of structure"]),
    ("MSS", "mss", "structure", ["market structure shift", "CHoCH", "change of character"]),
    ("Displacement", "displacement", "structure", ["impulsive move", "expansion"]),
    ("HTF bias", "htf-bias", "structure", ["higher timeframe bias", "daily bias", "bias"]),
    ("SMT divergence", "smt-divergence", "structure", ["SMT", "smart money technique divergence", "smt div"]),
    # Liquidity
    ("Liquidity sweep", "liquidity-sweep", "liquidity", ["sweep", "stop hunt", "stop run", "raid"]),
    ("BSL", "bsl", "liquidity", ["buy side liquidity", "buyside liquidity"]),
    ("SSL", "ssl", "liquidity", ["sell side liquidity", "sellside liquidity"]),
    ("Equal highs", "equal-highs", "liquidity", ["EQH", "double top liquidity", "relative equal highs"]),
    ("Equal lows", "equal-lows", "liquidity", ["EQL", "double bottom liquidity", "relative equal lows"]),
    ("Draw on liquidity", "draw-on-liquidity", "liquidity", ["DOL", "liquidity target"]),
    ("Judas swing", "judas-swing", "liquidity", ["judas", "false move"]),
    # Killzones
    ("Asia killzone", "asia-killzone", "killzone", ["asia session", "asian killzone", "asia kz"]),
    ("London killzone", "london-killzone", "killzone", ["london open", "london kz", "LOKZ"]),
    (
        "NY AM killzone",
        "ny-am-killzone",
        "killzone",
        ["new york am", "ny am", "nyam", "NY open", "NY AM session"],
    ),
    ("NY PM killzone", "ny-pm-killzone", "killzone", ["new york pm", "ny pm", "nypm", "NY PM session"]),
    ("London close", "london-close", "killzone", ["london close killzone", "LCKZ"]),
    # Entry models
    ("Silver Bullet", "silver-bullet", "entry_model", ["SB", "ICT silver bullet"]),
    ("2022 model", "2022-model", "entry_model", ["ict 2022 model", "2022 mentorship model"]),
    ("Unicorn", "unicorn", "entry_model", ["unicorn model", "breaker + fvg"]),
    ("Turtle soup", "turtle-soup", "entry_model", ["turtle soup entry", "false breakout"]),
    ("Power of 3", "power-of-3", "entry_model", ["PO3", "AMD", "accumulation manipulation distribution"]),
    # Confluences
    ("Time and price", "time-and-price", "confluence", ["time & price"]),
    ("Macro", "macro", "confluence", ["ict macro", "macro time"]),
    ("Opening range", "opening-range", "confluence", ["OR", "opening range gap", "ORG"]),
]


def upgrade() -> None:
    tags = sa.table(
        "tags",
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("category", sa.String),
        sa.column("synonyms", sa.JSON),
        sa.column("status", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        tags,
        [
            {
                "name": name,
                "slug": slug,
                "category": category,
                "synonyms": synonyms,
                "status": "approved",
                "created_at": now,
                "updated_at": now,
            }
            for name, slug, category, synonyms in SEED_TAGS
        ],
    )


def downgrade() -> None:
    slugs = ", ".join(f"'{slug}'" for _, slug, _, _ in SEED_TAGS)
    op.execute(f"DELETE FROM tags WHERE slug IN ({slugs})")
