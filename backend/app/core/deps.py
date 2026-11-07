"""FastAPI dependencies: database, current user, role checks and the list scope filter."""

from typing import Annotated, Literal, Protocol

from fastapi import Depends, HTTPException, Query, Request, Response
from sqlalchemy import Select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import User
from ..services import users as users_svc
from .ratelimit import RateLimiter
from .settings import get_settings

SESSION_COOKIE = "tp_session"
CSRF_COOKIE = "tp_csrf"
CSRF_HEADER = "X-CSRF-Token"

Scope = Literal["mine", "everyone", "others"]

Db = Annotated[Session, Depends(get_session)]


def set_session_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=s.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=s.cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_user(request: Request, response: Response, db: Db) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Sign in to continue.")
    sess = users_svc.find_session(db, token)
    if not sess:
        clear_session_cookie(response)
        raise HTTPException(401, "Your session has ended. Sign in again.")
    if not sess.user.is_active:
        db.delete(sess)
        db.commit()
        clear_session_cookie(response)
        raise HTTPException(403, "This account is deactivated.")
    if users_svc.touch_session(db, sess):
        set_session_cookie(response, token)  # sliding window: refresh the cookie's Max-Age too
    return sess.user


CurrentUser = Annotated[User, Depends(current_user)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admins only.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]

# The expensive endpoints (zip exports, the whole-database export, CSV import previews) share one modest
# per-user budget so a stuck retry loop or a script can't keep the single machine busy. Per user, not per
# IP: the four of us may share a network. Tests reset it between cases (conftest).
heavy_limiter = RateLimiter(limit=10, window_seconds=60)


def heavy_endpoint(user: CurrentUser) -> User:
    if not heavy_limiter.allow(str(user.id)):
        raise HTTPException(429, "You're doing that a lot. Wait a minute and try again.")
    return user


HeavyUser = Annotated[User, Depends(heavy_endpoint)]


class Owned(Protocol):
    owner_id: int


def require_owner_or_admin(record: Owned, user: User) -> None:
    """Members change only their own records; the admin changes anything."""
    if user.is_admin or record.owner_id == user.id:
        return
    raise HTTPException(403, "You can only change your own records.")


ScopeParam = Annotated[Scope, Query(description="mine | everyone | others")]


def apply_scope[T](stmt: Select[T], owner_column, scope: Scope, user: User) -> Select[T]:
    """Mine · Everyone · Others (F12). Everyone is the default and applies no filter."""
    if scope == "mine":
        return stmt.where(owner_column == user.id)
    if scope == "others":
        return stmt.where(owner_column != user.id)
    return stmt
