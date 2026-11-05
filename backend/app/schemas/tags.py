from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["pd_array", "entry_model", "liquidity", "structure", "killzone", "confluence", "other"]


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    category: Category
    synonyms: list[str]
    status: Literal["approved", "proposed"]
    created_by_id: int | None
    created_at: datetime
    updated_at: datetime


class TagCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    category: Category = "other"
    synonyms: list[str] = Field(default_factory=list, max_length=30)


class TagUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    category: Category | None = None
    synonyms: list[str] | None = Field(default=None, max_length=30)
    status: Literal["approved", "proposed"] | None = None


class TagMergeIn(BaseModel):
    into_id: int


class TagResolveOut(BaseModel):
    query: str
    tag: TagOut | None
