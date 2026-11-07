"""Team calendar (1.4): tasks, task_exceptions, task_completions.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _owned() -> list[sa.Column]:
    return [
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(16), nullable=False, server_default="other"),
        sa.Column("all_day", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tz", sa.String(48), nullable=False, server_default="Europe/London"),
        sa.Column("rrule", sa.String(300), nullable=True),
        *_owned(),
    )
    op.create_index("ix_tasks_owner_id", "tasks", ["owner_id"])
    op.create_index("ix_tasks_start_at", "tasks", ["start_at"])

    op.create_table(
        "task_exceptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("occurrence_date", sa.String(10), nullable=False),
        sa.Column("deleted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("all_day", sa.Boolean, nullable=True),
        sa.Column("title", sa.String(120), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "occurrence_date", name="uq_task_exception"),
    )
    op.create_index("ix_task_exceptions_task_id", "task_exceptions", ["task_id"])

    op.create_table(
        "task_completions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("occurrence_date", sa.String(10), nullable=False),
        sa.Column("completed_by_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "occurrence_date", name="uq_task_completion"),
    )
    op.create_index("ix_task_completions_task_id", "task_completions", ["task_id"])


def downgrade() -> None:
    op.drop_table("task_completions")
    op.drop_table("task_exceptions")
    op.drop_table("tasks")
