"""Breakeven threshold default ±$2 → ±$10 (Jamie, 6 Nov 2026: "stay in $, make it 10 up or down").

Accounts still on the old default move to 10; anyone who chose another value keeps it. Data only: new
accounts get 10 from the model default (every insert goes through the ORM), so the users table isn't
rebuilt (SQLite batch mode would recreate a table that every other table references). Stored trade
outcomes are re-labelled from P&L with each owner's threshold, so lists and chips agree with Analytics
(which always recomputes). Downgrade puts the old default back for accounts on 10.

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

RELABEL = """
UPDATE trades SET outcome = CASE
    WHEN pnl > (SELECT breakeven_threshold FROM users WHERE users.id = trades.owner_id) THEN 'win'
    WHEN pnl < -(SELECT breakeven_threshold FROM users WHERE users.id = trades.owner_id) THEN 'loss'
    ELSE 'breakeven'
END
WHERE pnl IS NOT NULL AND kind != 'missed'
"""


def upgrade() -> None:
    op.execute("UPDATE users SET breakeven_threshold = 10.0 WHERE breakeven_threshold = 2.0")
    op.execute(RELABEL)


def downgrade() -> None:
    op.execute("UPDATE users SET breakeven_threshold = 2.0 WHERE breakeven_threshold = 10.0")
    op.execute(RELABEL)
