"""Web Push sending (F7), behind a small `PushSender` protocol.

`WebPushSender` signs with the server's VAPID key and posts through pywebpush (which uses `requests`,
not our guarded httpx client), so tests never construct it: they monkeypatch `get_sender` to return a
`FakePushSender`. As a second guard the real sender refuses to send under TRADING_PORTAL_ENV=test.

The VAPID private key is read from settings only; it is never logged, returned or written anywhere.
"""

import base64
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Protocol

from cryptography.hazmat.primitives import serialization

from ..core.settings import get_settings
from .http import NetworkBlocked

log = logging.getLogger("trading_portal.push")

TTL_SECONDS = 900  # a pre-event alert is useless after ~15 minutes, so let the push service drop it
TIMEOUT_SECONDS = 10
GONE = (404, 410)


@dataclass(frozen=True)
class PushResult:
    status_code: int | None
    ok: bool
    gone: bool  # the push service says the subscription no longer exists: prune it
    error: str | None = None


class SubscriptionLike(Protocol):
    """What a sender needs from a subscription; a PushSubscription row satisfies it."""

    endpoint: str
    p256dh: str
    auth: str


class PushSender(Protocol):
    public_key: str | None

    def send(self, subscription: SubscriptionLike, payload: dict) -> PushResult: ...


# Only the browsers' own push services may be targets (SSRF guard: a member can't make the server POST
# to an internal address by registering a crafted "endpoint"). Checked at registration and at send time.
PUSH_HOSTS = (
    "fcm.googleapis.com",  # Chrome, Edge, Android
    "push.services.mozilla.com",  # Firefox (updates.push.services.mozilla.com)
    "push.apple.com",  # Safari and iOS home-screen apps (web.push.apple.com)
    "notify.windows.com",  # legacy Edge / Windows
)
TEST_PUSH_HOSTS = ("example.test",)


def allowed_push_endpoint(url: str) -> bool:
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if (
        parts.scheme != "https"
        or not host
        or parts.username
        or parts.password
        or parts.port not in (None, 443)
    ):
        return False
    hosts = PUSH_HOSTS + (TEST_PUSH_HOSTS if get_settings().env == "test" else ())
    return any(host == h or host.endswith("." + h) for h in hosts)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class WebPushSender:
    """The real sender. Construct only through `get_sender()`."""

    def __init__(self, private_key: str, subject: str, configured_public_key: str | None = None) -> None:
        from py_vapid import Vapid

        self._vapid = Vapid.from_string(private_key=private_key)
        self._subject = subject
        derived = _b64url(
            self._vapid.public_key.public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
            )
        )
        if configured_public_key and configured_public_key != derived:
            log.warning("VAPID_PUBLIC_KEY doesn't match VAPID_PRIVATE_KEY; using the private key's half")
        # Browsers subscribe with this key, so it must be the private key's own public half.
        self.public_key: str | None = derived

    def send(self, subscription: SubscriptionLike, payload: dict) -> PushResult:
        if get_settings().env == "test":
            raise NetworkBlocked("Real Web Push blocked in tests: use FakePushSender")
        if not allowed_push_endpoint(subscription.endpoint):
            return PushResult(None, False, True, "Not a known push service")
        import requests
        from pywebpush import WebPushException, webpush

        try:
            res = webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=json.dumps(payload, separators=(",", ":")),
                vapid_private_key=self._vapid,
                # A fresh dict every call: pywebpush writes `aud` (the endpoint's origin) and `exp` into it.
                vapid_claims={"sub": self._subject},
                ttl=TTL_SECONDS,
                headers={"Urgency": "high"},
                timeout=TIMEOUT_SECONDS,
            )
            code = getattr(res, "status_code", None)
            return PushResult(code, True, False)
        except WebPushException as exc:
            code = exc.status_code
            reason = getattr(exc.response, "reason", "") or ""
            return PushResult(
                code,
                False,
                code in GONE,
                f"Push service answered {code} {reason}".strip() if code else "Push failed",
            )
        except requests.RequestException as exc:
            # Never str(exc): it can carry the endpoint URL.
            return PushResult(None, False, False, f"Couldn't reach the push service ({type(exc).__name__})")


@dataclass
class FakePushSender:
    """Records every send. `statuses` maps an endpoint to the HTTP status the fake push service answers."""

    statuses: dict[str, int] = field(default_factory=dict)
    default_status: int = 201
    public_key: str | None = "BFakePublicKeyForTestsOnly"
    calls: list[tuple[str, dict]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def send(self, subscription: SubscriptionLike, payload: dict) -> PushResult:
        code = self.statuses.get(subscription.endpoint, self.default_status)
        with self._lock:
            self.calls.append((subscription.endpoint, payload))
        ok = 200 <= code < 300
        return PushResult(code, ok, code in GONE, None if ok else f"Push service answered {code}")

    def sent_to(self, endpoint: str) -> list[dict]:
        return [p for e, p in self.calls if e == endpoint]


def get_sender() -> PushSender | None:
    """The configured sender, or None when the VAPID keys aren't set (or don't load).

    Tests monkeypatch this (`monkeypatch.setattr(push, "get_sender", lambda: fake)`).
    """
    s = get_settings()
    if not (s.vapid_private_key and s.vapid_subject):
        return None
    try:
        return WebPushSender(s.vapid_private_key, s.vapid_subject, s.vapid_public_key)
    except Exception as exc:  # noqa: BLE001 — a malformed key must not take the app down
        log.warning("VAPID_PRIVATE_KEY couldn't be loaded (%s); push is off", type(exc).__name__)
        return None
