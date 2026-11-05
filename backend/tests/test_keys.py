"""Per-user key vault: encrypted at rest, last 4 only, never returned, never logged."""

from sqlalchemy import select

from app.models import AuditLog, UserApiKey
from app.services import keys as keys_svc

KEY = "td-live-ABCDEFGHIJKLMNOP-9876"


def test_set_list_test_delete(member_client, member, db) -> None:
    res = member_client.put("/api/me/keys/twelve_data", json={"key": KEY})
    assert res.status_code == 200
    assert res.json()["last4"] == "9876"
    assert KEY not in res.text

    rows = member_client.get("/api/me/keys").json()
    assert len(rows) == 1 and rows[0]["provider"] == "twelve_data" and "key" not in rows[0]

    stored = db.scalar(select(UserApiKey))
    assert KEY.encode() not in stored.ciphertext  # encrypted, not plaintext
    assert keys_svc.reveal_for_server_use(db, member, "twelve_data") == KEY  # server can use it

    tested = member_client.post("/api/me/keys/twelve_data/test")
    assert tested.status_code == 200 and tested.json()["ok"] is True
    assert member_client.get("/api/me/keys").json()[0]["last_test_ok"] is True

    assert member_client.delete("/api/me/keys/twelve_data").status_code == 200
    assert member_client.get("/api/me/keys").json() == []
    assert member_client.delete("/api/me/keys/twelve_data").status_code == 404
    db.expire_all()
    assert db.scalar(select(UserApiKey)).ciphertext == b""  # soft-deleted and wiped


def test_key_can_be_replaced_after_delete(member_client) -> None:
    member_client.put("/api/me/keys/twelve_data", json={"key": KEY})
    member_client.delete("/api/me/keys/twelve_data")
    res = member_client.put("/api/me/keys/twelve_data", json={"key": "another-key-5555"})
    assert res.status_code == 200 and res.json()["last4"] == "5555"


def test_keys_are_private_to_their_owner(member_client, admin_client, admin, member, db) -> None:
    member_client.put("/api/me/keys/twelve_data", json={"key": KEY})
    assert admin_client.get("/api/me/keys").json() == []
    assert keys_svc.reveal_for_server_use(db, admin, "twelve_data") is None


def test_plaintext_never_hits_the_audit_log(member_client, db) -> None:
    member_client.put("/api/me/keys/twelve_data", json={"key": KEY})
    for row in db.scalars(select(AuditLog)):
        assert KEY not in str(row.meta) and KEY not in (row.target_id or "")


def test_unknown_provider_and_short_key(member_client) -> None:
    assert member_client.put("/api/me/keys/nope", json={"key": KEY}).status_code == 422
    assert member_client.put("/api/me/keys/twelve_data", json={"key": "short"}).status_code == 400
