"""Push alerts (docs/build/prompt4-api.md → Alerts). Never carries a raw endpoint or push keys out."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AlertConfigOut(BaseModel):
    push_configured: bool
    vapid_public_key: str | None


class AlertPrefsOut(BaseModel):
    enabled: bool
    minutes_before: int
    currencies: list[str] | None  # None = my instruments' currencies
    effective_currencies: list[str]
    impacts: list[str]
    quiet_start: str | None
    quiet_end: str | None
    chime: bool


class AlertPrefsIn(BaseModel):
    """Every field optional; only the fields sent change. `currencies: null` means "my instruments'"."""

    enabled: bool | None = None
    minutes_before: int | None = Field(default=None, ge=1, le=120)
    currencies: list[str] | None = Field(default=None, max_length=40)
    impacts: list[str] | None = Field(default=None, max_length=3)
    quiet_start: str | None = Field(default=None, max_length=5)
    quiet_end: str | None = Field(default=None, max_length=5)
    chime: bool | None = None


class DeviceOut(BaseModel):
    id: int
    device_label: str
    created_at: datetime
    last_success_at: datetime | None
    last_error: str | None
    endpoint_hash: str


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2000)
    keys: SubscriptionKeys
    device_label: str | None = Field(default=None, max_length=80)

    @field_validator("endpoint")
    @classmethod
    def _https(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("https://"):
            raise ValueError("A push endpoint must be an https:// URL.")
        return v


class SubscriptionCreatedOut(BaseModel):
    id: int


class AlertTestIn(BaseModel):
    subscription_id: int | None = None


class AlertTestOut(BaseModel):
    sent: int
    failed: int
    pruned: int
