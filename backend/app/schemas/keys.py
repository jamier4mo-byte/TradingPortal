from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Provider = Literal["twelve_data"]


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    last4: str
    created_at: datetime
    updated_at: datetime
    last_tested_at: datetime | None
    last_test_ok: bool | None


class ApiKeySetIn(BaseModel):
    key: str = Field(min_length=1, max_length=500)


class ApiKeyTestOut(BaseModel):
    ok: bool
    tested_at: datetime
    message: str | None = None  # "Key works · 12 of 800 credits used today" / "Twelve Data rejected this key"
