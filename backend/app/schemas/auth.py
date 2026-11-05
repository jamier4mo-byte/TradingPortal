from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import Email


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    label: str
    role: Literal["admin", "member"]
    status: Literal["active", "deactivated"]
    colour_index: int
    motion_pref: Literal["full", "reduced", "off"]
    breakeven_threshold: float
    last_seen_at: datetime | None
    created_at: datetime


class PublicUserOut(BaseModel):
    """What other members see: enough for an owner chip."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    label: str
    status: Literal["active", "deactivated"]
    colour_index: int


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=200)


class AcceptInviteIn(BaseModel):
    token: str
    email: Email
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class InvitePeekOut(BaseModel):
    role: str
    email: str | None
    expires_at: datetime


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=1, max_length=200)


class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    motion_pref: Literal["full", "reduced", "off"] | None = None
    breakeven_threshold: float | None = Field(default=None, ge=0, le=100)


class PasskeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    backed_up: bool
    created_at: datetime
    last_used_at: datetime | None


class PasskeyBeginOut(BaseModel):
    challenge_key: str
    options: dict[str, Any]


class PasskeyFinishRegistrationIn(BaseModel):
    challenge_key: str
    credential: dict[str, Any]
    name: str = "Passkey"


class PasskeyFinishLoginIn(BaseModel):
    challenge_key: str
    credential: dict[str, Any]


class OkOut(BaseModel):
    ok: bool = True
    message: str | None = None
