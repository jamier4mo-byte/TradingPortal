"""Push alerts: VAPID config, preferences, devices and a test send (docs/build/prompt4-api.md → Alerts).

Responses never include a subscription's endpoint or keys: a device is identified by its id and a short
`endpoint_hash`.
"""

from fastapi import APIRouter, HTTPException, Request

from ..core.deps import CurrentUser, Db
from ..models import AlertPrefs, PushSubscription
from ..schemas.alerts import (
    AlertConfigOut,
    AlertPrefsIn,
    AlertPrefsOut,
    AlertTestIn,
    AlertTestOut,
    DeviceOut,
    SubscriptionCreatedOut,
    SubscriptionIn,
)
from ..schemas.auth import OkOut
from ..services import alerts as alerts_svc
from ..services import push
from ..services.alerts import AlertError

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _http(exc: AlertError) -> HTTPException:
    return HTTPException(exc.status, exc.message)


def _prefs_out(db, prefs: AlertPrefs) -> AlertPrefsOut:
    return AlertPrefsOut(
        enabled=prefs.enabled,
        minutes_before=prefs.minutes_before,
        currencies=prefs.currencies,
        effective_currencies=sorted(alerts_svc.effective_currencies(db, prefs)),
        impacts=list(prefs.impacts),
        quiet_start=prefs.quiet_start,
        quiet_end=prefs.quiet_end,
        chime=prefs.chime,
    )


def _device_out(sub: PushSubscription) -> DeviceOut:
    return DeviceOut(
        id=sub.id,
        device_label=sub.device_label,
        created_at=sub.created_at,
        last_success_at=sub.last_success_at,
        last_error=sub.last_error,
        endpoint_hash=alerts_svc.endpoint_hash(sub.endpoint),
    )


@router.get("/config", response_model=AlertConfigOut)
def config(_: CurrentUser) -> AlertConfigOut:
    sender = push.get_sender()
    return AlertConfigOut(
        push_configured=sender is not None, vapid_public_key=sender.public_key if sender else None
    )


@router.get("/prefs", response_model=AlertPrefsOut)
def get_prefs(user: CurrentUser, db: Db) -> AlertPrefsOut:
    return _prefs_out(db, alerts_svc.get_prefs(db, user))


@router.put("/prefs", response_model=AlertPrefsOut)
def put_prefs(body: AlertPrefsIn, user: CurrentUser, db: Db) -> AlertPrefsOut:
    changes = {name: getattr(body, name) for name in body.model_fields_set}
    try:
        prefs = alerts_svc.save_prefs(db, user, changes)
    except AlertError as exc:
        db.rollback()
        raise _http(exc) from exc
    return _prefs_out(db, prefs)


@router.get("/devices", response_model=list[DeviceOut])
def devices(user: CurrentUser, db: Db) -> list[DeviceOut]:
    return [_device_out(s) for s in alerts_svc.list_subscriptions(db, user)]


@router.post("/subscriptions", response_model=SubscriptionCreatedOut, status_code=201)
def subscribe(body: SubscriptionIn, request: Request, user: CurrentUser, db: Db) -> SubscriptionCreatedOut:
    sub = alerts_svc.upsert_subscription(
        db,
        user,
        endpoint=body.endpoint,
        p256dh=body.keys.p256dh,
        auth=body.keys.auth,
        device_label=body.device_label,
        user_agent=request.headers.get("user-agent"),
    )
    return SubscriptionCreatedOut(id=sub.id)


@router.delete("/subscriptions/{subscription_id}", response_model=OkOut)
def unsubscribe(subscription_id: int, user: CurrentUser, db: Db) -> OkOut:
    try:
        alerts_svc.delete_subscription(db, user, subscription_id)
    except AlertError as exc:
        raise _http(exc) from exc
    return OkOut()


@router.post("/test", response_model=AlertTestOut)
def test_send(user: CurrentUser, db: Db, body: AlertTestIn | None = None) -> AlertTestOut:
    try:
        counts = alerts_svc.send_test(db, user, body.subscription_id if body else None)
    except AlertError as exc:
        raise _http(exc) from exc
    return AlertTestOut(**counts)
