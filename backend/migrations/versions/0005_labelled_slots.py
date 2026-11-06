"""Three labelled screenshots per trade (HTF, Entry, Outcome) and a manual completed mark.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("trades") as batch:
        batch.add_column(sa.Column("annotated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE screenshots SET slot = 'outcome' WHERE slot = 'exit'")


def downgrade() -> None:
    op.execute("UPDATE screenshots SET slot = 'exit' WHERE slot = 'outcome'")
    with op.batch_alter_table("trades") as batch:
        batch.drop_column("annotated_at")
