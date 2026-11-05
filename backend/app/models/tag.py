from typing import Literal

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, SoftDeleteMixin, TimestampMixin

TAG_CATEGORIES = ("pd_array", "entry_model", "liquidity", "structure", "killzone", "confluence", "other")
TagCategory = Literal["pd_array", "entry_model", "liquidity", "structure", "killzone", "confluence", "other"]
TagStatus = Literal["approved", "proposed"]


class Tag(TimestampMixin, SoftDeleteMixin, Base):
    """One shared ICT/SMC vocabulary. Admin curates; members propose."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False, default="other")
    synonyms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="approved")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("tags.id"), nullable=True)
