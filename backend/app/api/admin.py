"""Admin only: invites, users, roles, deactivation and reset links."""

from fastapi import APIRouter, HTTPException, Request

from ..core.deps import AdminUser, CurrentUser, Db
from ..core.settings import get_settings
from ..models import User
from ..schemas.admin import InviteCreateIn, InviteOut, ResetLinkOut, RoleIn, StatusIn
from ..schemas.auth import PublicUserOut, UserOut
from ..services import users as users_svc
from ..services.users import AuthError
from .errors import http

router = APIRouter(tags=["admin"])


def _origin(request: Request) -> str:
    """The front end's origin for links the admin will copy.

    The request's Origin header is used only when it is one of the configured TRADING_PORTAL_ORIGINS (the
    same allow-list WebAuthn trusts), so a spoofed Origin or Host header can't point an invite link at
    another site. Otherwise the first configured origin, and only as a last resort the request host.
    """
    allowed = [o.rstrip("/") for o in get_settings().origins]
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin and origin in allowed:
        return origin
    if allowed:
        return allowed[0]
    return str(request.base_url).rstrip("/")


def _get_user(db: Db, user_id: int) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "No such user.")
    return user


@router.get("/users", response_model=list[PublicUserOut])
def list_users_public(_: CurrentUser, db: Db) -> list[PublicUserOut]:
    """Every signed-in user can see who's who (for owner chips and filters)."""
    return [PublicUserOut.model_validate(u) for u in users_svc.list_users(db)]


@router.get("/admin/users", response_model=list[UserOut])
def list_users(_: AdminUser, db: Db) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in users_svc.list_users(db)]


@router.post("/admin/invites", response_model=InviteOut, status_code=201)
def create_invite(body: InviteCreateIn, admin: AdminUser, request: Request, db: Db) -> InviteOut:
    try:
        invite, token = users_svc.create_invite(db, admin, role=body.role, email=body.email)
    except AuthError as exc:
        raise http(exc) from exc
    return InviteOut(
        id=invite.id,
        role=invite.role,
        email=invite.email,
        expires_at=invite.expires_at,
        url=f"{_origin(request)}/invite/{token}",
    )


@router.patch("/admin/users/{user_id}/role", response_model=UserOut)
def set_role(user_id: int, body: RoleIn, admin: AdminUser, db: Db) -> UserOut:
    user = _get_user(db, user_id)
    try:
        users_svc.set_role(db, admin, user, body.role)
    except AuthError as exc:
        raise http(exc) from exc
    return UserOut.model_validate(user)


@router.patch("/admin/users/{user_id}/status", response_model=UserOut)
def set_status(user_id: int, body: StatusIn, admin: AdminUser, db: Db) -> UserOut:
    user = _get_user(db, user_id)
    try:
        users_svc.set_status(db, admin, user, body.status)
    except AuthError as exc:
        raise http(exc) from exc
    return UserOut.model_validate(user)


@router.post("/admin/users/{user_id}/reset-link", response_model=ResetLinkOut, status_code=201)
def create_reset_link(user_id: int, admin: AdminUser, request: Request, db: Db) -> ResetLinkOut:
    user = _get_user(db, user_id)
    if not user.is_active:
        raise HTTPException(409, "Reactivate the account before issuing a reset link.")
    reset, token = users_svc.create_reset(db, admin, user)
    return ResetLinkOut(user_id=user.id, expires_at=reset.expires_at, url=f"{_origin(request)}/reset/{token}")
