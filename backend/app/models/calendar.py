"""Team calendar (Foundations 1.4): tasks, per-occurrence exceptions and completions.

A task is one row whether it repeats or not. `rrule` holds an RFC 5545 RRULE (without the `RRULE:`
prefix) and is expanded at read time in the task's own zone (`tz`), so a weekly 09:00 Europe/London task
stays 09:00 UK across the clock changes. Editing or deleting "this occurrence" writes a `task_exceptions`
row keyed by the occurrence's original local date; marking an occurrence done writes `task_completions`.
"""

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, OwnedRecordMixin, UTCDateTime

CATEGORIES = ("backtesting", "review", "admin", "other")
CATEGORY_LABELS = {"backtesting": "Backtesting", "review": "Review", "admin": "Admin", "other": "Other"}
DEFAULT_TZ = "Europe/London"


class Task(OwnedRecordMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False, default="other")
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    start_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
    end_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    tz: Mapped[str] = mapped_column(String(48), nullable=False, default=DEFAULT_TZ)
    rrule: Mapped[str | None] = mapped_column(String(300), nullable=True)

    exceptions: Mapped[list["TaskException"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    completions: Mapped[list["TaskCompletion"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    @property
    def recurring(self) -> bool:
        return bool(self.rrule)


class TaskException(Base):
    """One occurrence of a recurring task that was moved, edited or deleted on its own."""

    __tablename__ = "task_exceptions"
    __table_args__ = (UniqueConstraint("task_id", "occurrence_date", name="uq_task_exception"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurrence_date: Mapped[str] = mapped_column(String(10), nullable=False)  # original local YYYY-MM-DD
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    start_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    all_day: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    task: Mapped[Task] = relationship(back_populates="exceptions")


class TaskCompletion(Base):
    __tablename__ = "task_completions"
    __table_args__ = (UniqueConstraint("task_id", "occurrence_date", name="uq_task_completion"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurrence_date: Mapped[str] = mapped_column(String(10), nullable=False)
    completed_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    task: Mapped[Task] = relationship(back_populates="completions")
