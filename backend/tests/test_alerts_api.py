"""`/api/alerts`: config, prefs, devices, subscriptions and the test send. Never leaks endpoints or keys."""

import hashlib

import pytest

from app.services import push

from .conftest import make_client, sign_in

ENDPOINT = "https://fcm.googleapis.example.test/wp/abc123"
P256DH = "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM"
AUTH = "tBHItJI5svbpez7KI4CCXg"
SUB = {"endpoint": ENDPOINT, "keys": {"p256dh": P256DH, "auth": AUTH}, "device_label": "Jamie's iPhone"}


@pytest.fixture
def fake(monkeypatch) -> push.FakePushSender:
    sender = push.FakePushSender(public_key="BPublicKeyForTests")
    monkeypatch.setattr(push, "get_sender", lambda: sender)
    return sender


@pytest.fixture
def other_client(other_member):
    c = make_client()
    sign_in(c, other_member.email)
    return c


def assert_no_secrets(res):
    for secret in (ENDPOINT, P256DH, AUTH, "abc123"):
        assert secret not in res.text


def test_needs_sign_in(client):
    assert client.get("/api/alerts/config").status_code == 401
    assert client.get("/api/alerts/prefs").status_code == 401


def test_config_without_vapid(member_client):
    assert member_client.get("/api/alerts/config").json() == {
        "push_configured": False,
        "vapid_public_key": None,
    }


def test_config_with_vapid(member_client, fake):
    assert member_client.get("/api/alerts/config").json() == {
        "push_configured": True,
        "vapid_public_key": "BPublicKeyForTests",
    }


# ---- prefs -------------------------------------------------------------------------------------


def test_prefs_default_to_off(member_client):
    body = member_client.get("/api/alerts/prefs").json()
    assert body["enabled"] is False
    assert body["minutes_before"] == 15
    assert body["currencies"] is None
    assert body["impacts"] == ["high"]
    assert body["quiet_start"] is None and body["quiet_end"] is None
    assert body["chime"] is False
    assert {"USD", "EUR", "GBP"} <= set(body["effective_currencies"])


def test_prefs_round_trip(member_client):
    res = member_client.put(
        "/api/alerts/prefs",
        json={
            "enabled": True,
            "minutes_before": 30,
            "currencies": ["usd", "JPY", "USD"],
            "impacts": ["medium", "high"],
            "quiet_start": "22:00",
            "quiet_end": "07:00",
            "chime": True,
        },
    )
    assert res.status_code == 200, res.text
    expected = {
        "enabled": True,
        "minutes_before": 30,
        "currencies": ["USD", "JPY"],
        "effective_currencies": ["JPY", "USD"],
        "impacts": ["high", "medium"],
        "quiet_start": "22:00",
        "quiet_end": "07:00",
        "chime": True,
    }
    assert res.json() == expected
    assert member_client.get("/api/alerts/prefs").json() == expected

    # Only the fields sent change; currencies null goes back to "my instruments'".
    res = member_client.put(
        "/api/alerts/prefs", json={"currencies": None, "quiet_start": None, "quiet_end": None}
    )
    body = res.json()
    assert body["currencies"] is None and "EUR" in body["effective_currencies"]
    assert body["quiet_start"] is None and body["minutes_before"] == 30 and body["enabled"] is True


@pytest.mark.parametrize(
    "bad",
    [
        {"minutes_before": 0},
        {"minutes_before": 121},
        {"impacts": ["extreme"]},
        {"impacts": []},
        {"currencies": []},
        {"currencies": ["US-D"]},
        {"quiet_start": "25:00", "quiet_end": "07:00"},
        {"quiet_start": "7am", "quiet_end": "08:00"},
        {"quiet_start": "22:00"},  # needs an end too
    ],
)
def test_prefs_validation(member_client, bad):
    res = member_client.put("/api/alerts/prefs", json=bad)
    assert res.status_code == 422, res.text
    assert member_client.get("/api/alerts/prefs").json()["enabled"] is False  # nothing half-saved


def test_minutes_edges_are_allowed(member_client):
    assert member_client.put("/api/alerts/prefs", json={"minutes_before": 1}).status_code == 200
    assert member_client.put("/api/alerts/prefs", json={"minutes_before": 120}).status_code == 200


# ---- devices -----------------------------------------------------------------------------------


def test_subscribe_upserts_and_lists_without_secrets(member_client):
    res = member_client.post("/api/alerts/subscriptions", json=SUB)
    assert res.status_code == 201
    sub_id = res.json()["id"]
    assert res.json() == {"id": sub_id}

    again = member_client.post("/api/alerts/subscriptions", json={**SUB, "device_label": "iPhone 16"})
    assert again.status_code == 201 and again.json()["id"] == sub_id

    devices = member_client.get("/api/alerts/devices")
    assert_no_secrets(devices)
    [device] = devices.json()
    assert device["id"] == sub_id
    assert device["device_label"] == "iPhone 16"
    assert device["endpoint_hash"] == hashlib.sha256(ENDPOINT.encode()).hexdigest()[:12]
    assert set(device) == {
        "id",
        "device_label",
        "created_at",
        "last_success_at",
        "last_error",
        "endpoint_hash",
    }


def test_subscribe_validation(member_client):
    insecure = {**SUB, "endpoint": "http://push.example.test/x"}
    assert member_client.post("/api/alerts/subscriptions", json=insecure).status_code == 422
    no_keys = {"endpoint": ENDPOINT, "keys": {"p256dh": "", "auth": AUTH}}
    assert member_client.post("/api/alerts/subscriptions", json=no_keys).status_code == 422
    unlabelled = {"endpoint": ENDPOINT, "keys": SUB["keys"]}
    assert member_client.post("/api/alerts/subscriptions", json=unlabelled).status_code == 201
    assert member_client.get("/api/alerts/devices").json()[0]["device_label"] == "This device"


def test_an_endpoint_registered_by_someone_else_moves_to_them(member_client, other_client):
    sub_id = member_client.post("/api/alerts/subscriptions", json=SUB).json()["id"]
    assert other_client.post("/api/alerts/subscriptions", json=SUB).json()["id"] == sub_id
    assert member_client.get("/api/alerts/devices").json() == []
    assert [d["id"] for d in other_client.get("/api/alerts/devices").json()] == [sub_id]


def test_delete_own_only(member_client, other_client):
    sub_id = member_client.post("/api/alerts/subscriptions", json=SUB).json()["id"]
    res = other_client.delete(f"/api/alerts/subscriptions/{sub_id}")
    assert res.status_code == 404
    assert len(member_client.get("/api/alerts/devices").json()) == 1
    assert member_client.delete(f"/api/alerts/subscriptions/{sub_id}").json()["ok"] is True
    assert member_client.get("/api/alerts/devices").json() == []
    assert member_client.delete(f"/api/alerts/subscriptions/{sub_id}").status_code == 404


# ---- test send ---------------------------------------------------------------------------------


def test_test_send_without_vapid(member_client):
    member_client.post("/api/alerts/subscriptions", json=SUB)
    res = member_client.post("/api/alerts/test", json={})
    assert res.status_code == 503
    assert res.json()["detail"] == "Push isn't set up on the server yet (VAPID keys missing)."


def test_test_send_to_every_device(member_client, fake):
    member_client.post("/api/alerts/subscriptions", json=SUB)
    gone = {**SUB, "endpoint": "https://push.example.test/gone", "device_label": "Old laptop"}
    member_client.post("/api/alerts/subscriptions", json=gone)
    fake.statuses[gone["endpoint"]] = 410

    res = member_client.post("/api/alerts/test", json={})
    assert res.json() == {"sent": 1, "failed": 0, "pruned": 1}
    assert_no_secrets(res)
    payload = fake.sent_to(ENDPOINT)[0]
    assert payload["title"] == "Test alert · Trading Portal"
    assert payload["url"] == "/settings/alerts"

    [device] = member_client.get("/api/alerts/devices").json()
    assert device["device_label"] == "Jamie's iPhone" and device["last_success_at"] is not None


def test_test_send_to_one_device(member_client, other_client, fake):
    a = member_client.post("/api/alerts/subscriptions", json=SUB).json()["id"]
    member_client.post("/api/alerts/subscriptions", json={**SUB, "endpoint": "https://push.example.test/b"})
    assert member_client.post("/api/alerts/test", json={"subscription_id": a}).json()["sent"] == 1
    assert [e for e, _ in fake.calls] == [ENDPOINT]
    assert other_client.post("/api/alerts/test", json={"subscription_id": a}).status_code == 404


def test_test_send_failure_is_shown_on_the_device(member_client, fake):
    member_client.post("/api/alerts/subscriptions", json=SUB)
    fake.statuses[ENDPOINT] = 500
    assert member_client.post("/api/alerts/test", json={}).json() == {"sent": 0, "failed": 1, "pruned": 0}
    assert member_client.get("/api/alerts/devices").json()[0]["last_error"] == "Push service answered 500"


def test_test_send_with_no_devices(member_client, fake):
    res = member_client.post("/api/alerts/test", json={})
    assert res.status_code == 409
    assert "No devices" in res.json()["detail"]


def test_only_browser_push_services_are_accepted_as_endpoints(admin_client):
    keys = {"p256dh": "BOr" + "A" * 84, "auth": "x" * 22}
    for bad in (
        "http://fcm.googleapis.com/fcm/send/abc",
        "https://169.254.169.254/latest/meta-data",
        "https://localhost/hook",
        "https://internal.fly.dev/api",
        "https://fcm.googleapis.com.evil.test/x",
        "https://user:pw@fcm.googleapis.com/x",
        "https://fcm.googleapis.com:8443/x",
    ):
        res = admin_client.post("/api/alerts/subscriptions", json={"endpoint": bad, "keys": keys})
        assert res.status_code == 422, bad
    for good in (
        "https://fcm.googleapis.com/fcm/send/abc",
        "https://updates.push.services.mozilla.com/wpush/v2/abc",
        "https://web.push.apple.com/QH1",
    ):
        res = admin_client.post("/api/alerts/subscriptions", json={"endpoint": good, "keys": keys})
        assert res.status_code == 201, (good, res.text)
