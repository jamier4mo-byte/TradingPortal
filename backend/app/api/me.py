"""The signed-in user's own settings, password, passkeys and API keys."""

import json

from fastapi import APIRouter

from ..core.deps import CurrentUser, Db
from ..schemas.auth import (
    ChangePasswordIn,
    OkOut,
    PasskeyBeginOut,
    PasskeyFinishRegistrationIn,
    PasskeyOut,
    ProfileIn,
    UserOut,
)
from ..schemas.keys import ApiKeyOut, ApiKeySetIn, ApiKeyTestOut, Provider
from ..services import audit
from ..services import keys as keys_svc
from ..services import passkeys as passkeys_svc
from ..services import users as users_svc
from ..services.keys import KeyError_
from ..services.passkeys import PasskeyError
from ..services.users import AuthError
from .errors import http

router = APIRouter(prefix="/me", tags=["me"])


@router.patch("", response_model=UserOut)
def update_profile(body: ProfileIn, user: CurrentUser, db: Db) -> UserOut:
    changed = body.model_dump(exclude_none=True)
    for field, value in changed.items():
        setattr(user, field, value.strip() if isinstance(value, str) else value)
    if changed:
        audit.record(
            db, "user.profile_updated", actor=user, target_type="user", target_id=user.id, meta=changed
        )
        db.commit()
    return UserOut.model_validate(user)


@router.post("/password", response_model=OkOut)
def change_password(body: ChangePasswordIn, user: CurrentUser, db: Db) -> OkOut:
    try:
        users_svc.change_password(db, user, body.current_password, body.new_password)
    except AuthError as exc:
        raise http(exc) from exc
    return OkOut(message="Password changed. Other devices have been signed out.")


# ---- passkeys ----------------------------------------------------------------------------------


@router.get("/passkeys", response_model=list[PasskeyOut])
def list_passkeys(user: CurrentUser, db: Db) -> list[PasskeyOut]:
    return [PasskeyOut.model_validate(p) for p in passkeys_svc.list_passkeys(db, user)]


@router.post("/passkeys/begin", response_model=PasskeyBeginOut)
def passkey_register_begin(user: CurrentUser, db: Db) -> PasskeyBeginOut:
    options_json, key = passkeys_svc.begin_registration(db, user)
    return PasskeyBeginOut(challenge_key=key, options=json.loads(options_json))


@router.post("/passkeys/finish", response_model=PasskeyOut, status_code=201)
def passkey_register_finish(body: PasskeyFinishRegistrationIn, user: CurrentUser, db: Db) -> PasskeyOut:
    try:
        passkey = passkeys_svc.finish_registration(
            db, user, challenge_key=body.challenge_key, credential=body.credential, name=body.name
        )
    except PasskeyError as exc:
        raise http(exc) from exc
    return PasskeyOut.model_validate(passkey)


@router.delete("/passkeys/{passkey_id}", response_model=OkOut)
def delete_passkey(passkey_id: int, user: CurrentUser, db: Db) -> OkOut:
    try:
        passkeys_svc.delete_passkey(db, user, passkey_id)
    except PasskeyError as exc:
        raise http(exc) from exc
    return OkOut()


# ---- API-key vault -------------------------------------------------------------------------------


@router.get("/keys", response_model=list[ApiKeyOut])
def list_keys(user: CurrentUser, db: Db) -> list[ApiKeyOut]:
    return [ApiKeyOut.model_validate(k) for k in keys_svc.list_keys(db, user)]


@router.put("/keys/{provider}", response_model=ApiKeyOut)
def set_key(provider: Provider, body: ApiKeySetIn, user: CurrentUser, db: Db) -> ApiKeyOut:
    try:
        row = keys_svc.set_key(db, user, provider, body.key)
    except KeyError_ as exc:
        raise http(exc) from exc
    return ApiKeyOut.model_validate(row)


@router.delete("/keys/{provider}", response_model=OkOut)
def delete_key(provider: Provider, user: CurrentUser, db: Db) -> OkOut:
    try:
        keys_svc.delete_key(db, user, provider)
    except KeyError_ as exc:
        raise http(exc) from exc
    return OkOut()


@router.post("/keys/{provider}/test", response_model=ApiKeyTestOut)
def test_key(provider: Provider, user: CurrentUser, db: Db) -> ApiKeyTestOut:
    try:
        ok = keys_svc.test_key(db, user, provider)
    except KeyError_ as exc:
        raise http(exc) from exc
    return ApiKeyTestOut(ok=ok, tested_at=users_svc.utcnow())
