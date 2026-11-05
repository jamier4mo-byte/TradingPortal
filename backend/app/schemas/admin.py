from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .common import Email


class InviteCreateIn(BaseModel):
    role: Literal["admin", "member"] = "member"
    email: Email | None = None


class InviteOut(BaseModel):
    id: int
    role: str
    email: str | None
    expires_at: datetime
    url: str  # shown once; the admin copies it


class ResetLinkOut(BaseModel):
    user_id: int
    expires_at: datetime
    url: str


class RoleIn(BaseModel):
    role: Literal["admin", "member"]


class StatusIn(BaseModel):
    status: Literal["active", "deactivated"]
