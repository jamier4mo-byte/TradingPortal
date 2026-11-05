"""Sign-in, sign-out, invites, resets and passkey login. Unauthenticated routes are rate-limited per IP."""

import json

from fastapi import APIRouter, HTTPException, Request, Response

from ..core.csrf import issue_csrf_cookie
from ..core.deps import SESSION_COOKIE, CurrentUser, Db, clear_session_cookie, set_session_cookie
from ..core.ratelimit import RateLimiter
from ..core.settings import get_settings
from ..schemas.auth import (
    AcceptInviteIn,
    InvitePeekOut,
    LoginIn,
    OkOut,
    PasskeyBeginOut,
    PasskeyFinishLoginIn,
    ResetIn,
    UserOut,
)
from ..services import passkeys as passkeys_svc
from ..services import users as users_svc
from ..services.passkeys import PasskeyError
from ..services.users import AuthError
from .errors import http

router = APIRouter(prefix="/auth", tags=["auth"])

login_limiter = RateLimiter(limit=get_settings().login_rate_per_minute, window_seconds=60)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("fly-client-ip") or request.headers.get("x-forwarded-for", "")
    return (forwarded.split(",")[0].strip() if forwarded else None) or (
        request.client.host if request.client else "?"
    )


def _limit(request: Request) -> None:
    if not login_limiter.allow(_client_ip(request)):
        raise HTTPException(429, "Too many sign-in attempts from this network. Wait a minute and try again.")


def _sign_in(db: Db, request: Request, response: Response, user) -> UserOut:
    token = users_svc.create_session(db, user, request.headers.get("user-agent"))
    set_session_cookie(response, token)
    issue_csrf_cookie(response)
    return UserOut.model_validate(user)


@router.get("/csrf", response_model=OkOut)
def csrf(request: Request, response: Response) -> OkOut:
    """Make sure the browser has a CSRF cookie before its first unsafe call."""
    if "tp_csrf" not in request.cookies:
        issue_csrf_cookie(response)
    return OkOut()


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Db) -> UserOut:
    _limit(request)
    try:
        user = users_svc.authenticate(db, body.email, body.password)
    except AuthError as exc:
        raise http(exc) from exc
    return _sign_in(db, request, response, user)


@router.post("/logout", response_model=OkOut)
def logout(request: Request, response: Response, db: Db) -> OkOut:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        users_svc.revoke_session(db, token)
    clear_session_cookie(response)
    return OkOut()


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.get("/invite/{token}", response_model=InvitePeekOut)
def peek_invite(token: str, request: Request, db: Db) -> InvitePeekOut:
    _limit(request)
    try:
        invite = users_svc.peek_invite(db, token)
    except AuthError as exc:
        raise http(exc) from exc
    return InvitePeekOut(role=invite.role, email=invite.email, expires_at=invite.expires_at)


@router.post("/invite/accept", response_model=UserOut)
def accept_invite(body: AcceptInviteIn, request: Request, response: Response, db: Db) -> UserOut:
    _limit(request)
    try:
        user = users_svc.accept_invite(
            db, body.token, email=body.email, display_name=body.display_name, password=body.password
        )
    except AuthError as exc:
        raise http(exc) from exc
    return _sign_in(db, request, response, user)


@router.post("/reset", response_model=UserOut)
def reset_password(body: ResetIn, request: Request, response: Response, db: Db) -> UserOut:
    _limit(request)
    try:
        user = users_svc.use_reset(db, body.token, body.password)
    except AuthError as exc:
        raise http(exc) from exc
    return _sign_in(db, request, response, user)


@router.post("/passkey/login/begin", response_model=PasskeyBeginOut)
def passkey_login_begin(request: Request, db: Db) -> PasskeyBeginOut:
    _limit(request)
    options_json, key = passkeys_svc.begin_authentication(db)
    return PasskeyBeginOut(challenge_key=key, options=json.loads(options_json))


@router.post("/passkey/login/finish", response_model=UserOut)
def passkey_login_finish(body: PasskeyFinishLoginIn, request: Request, response: Response, db: Db) -> UserOut:
    _limit(request)
    try:
        user = passkeys_svc.finish_authentication(
            db, challenge_key=body.challenge_key, credential=body.credential
        )
    except PasskeyError as exc:
        raise http(exc) from exc
    return _sign_in(db, request, response, user)
