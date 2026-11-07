"""Sign-in, sessions, lockout, CSRF, invites and resets."""

from datetime import timedelta

from sqlalchemy import select

from app.core.deps import CSRF_COOKIE, SESSION_COOKIE
from app.core.security import hash_token, utcnow
from app.core.settings import get_settings
from app.models import AuditLog, Session, User
from tests.conftest import PASSWORD, make_client, make_user, sign_in


def test_login_sets_httponly_cookie_and_returns_me(client, admin) -> None:
    res = sign_in(client, admin.email)
    assert res.json()["role"] == "admin"
    cookie = res.headers.get("set-cookie", "")
    assert (
        SESSION_COOKIE in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie.replace("Lax", "lax")
    )
    assert client.get("/api/auth/me").json()["email"] == admin.email


def test_wrong_password_and_unknown_email_look_the_same(client, admin) -> None:
    a = client.post("/api/auth/login", json={"email": admin.email, "password": "nope-nope-nope"})
    b = client.post("/api/auth/login", json={"email": "ghost@example.test", "password": "nope-nope-nope"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_me_requires_a_session(client) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_logout_revokes_the_server_session(client, admin, db) -> None:
    sign_in(client, admin.email)
    assert db.scalar(select(Session)) is not None
    client.post("/api/auth/logout")
    db.expire_all()
    assert db.scalar(select(Session)) is None
    assert client.get("/api/auth/me").status_code == 401


def test_lockout_after_five_failures_for_fifteen_minutes(client, admin, db) -> None:
    for _ in range(5):
        res = client.post("/api/auth/login", json={"email": admin.email, "password": "wrong-wrong-1"})
        assert res.status_code == 401
    locked = client.post("/api/auth/login", json={"email": admin.email, "password": PASSWORD})
    assert locked.status_code == 423
    db.expire_all()
    user = db.get(User, admin.id)
    assert user.locked_until is not None
    remaining = user.locked_until - utcnow()
    assert timedelta(minutes=14) < remaining <= timedelta(minutes=15)
    assert db.scalar(select(AuditLog).where(AuditLog.action == "auth.locked")) is not None
    # Once the lock passes, the right password works again
    user.locked_until = utcnow() - timedelta(seconds=1)
    db.commit()
    assert (
        client.post("/api/auth/login", json={"email": admin.email, "password": PASSWORD}).status_code == 200
    )


def test_login_is_rate_limited_per_ip(client, admin) -> None:
    limit = get_settings().login_rate_per_minute
    for _ in range(limit):
        client.post("/api/auth/login", json={"email": "x@example.test", "password": "whatever-123"})
    assert (
        client.post("/api/auth/login", json={"email": admin.email, "password": PASSWORD}).status_code == 429
    )


def test_unsafe_methods_need_the_csrf_double_submit(admin_client) -> None:
    # header missing
    assert admin_client.request("POST", "/api/auth/logout", no_csrf=True).status_code == 403
    # header present but wrong
    res = admin_client.request(
        "POST", "/api/auth/logout", no_csrf=True, headers={"X-CSRF-Token": "not-the-cookie"}
    )
    assert res.status_code == 403
    # still signed in
    assert admin_client.get("/api/auth/me").status_code == 200
    # cookie is readable by JS (not HttpOnly)
    assert admin_client.cookies.get(CSRF_COOKIE)


def test_session_slides_after_a_day_of_use(admin_client, db) -> None:
    sess = db.scalar(select(Session))
    original_expiry = sess.expires_at
    # Pretend the session was last used 2 days ago
    sess.last_used_at = utcnow() - timedelta(days=2)
    sess.expires_at = utcnow() + timedelta(days=28)
    db.commit()
    res = admin_client.get("/api/auth/me")
    assert res.status_code == 200
    assert SESSION_COOKIE in res.headers.get("set-cookie", "")  # cookie Max-Age refreshed too
    db.expire_all()
    assert db.get(Session, sess.id).expires_at > original_expiry - timedelta(seconds=5)
    assert db.get(Session, sess.id).expires_at >= utcnow() + timedelta(days=29, hours=23)


def test_expired_session_is_rejected(admin_client, db) -> None:
    sess = db.scalar(select(Session))
    sess.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert admin_client.get("/api/auth/me").status_code == 401


def test_deactivated_user_is_signed_out_and_cannot_sign_in(admin_client, member, db) -> None:
    m = make_client()
    sign_in(m, member.email)
    assert m.get("/api/auth/me").status_code == 200
    res = admin_client.patch(f"/api/admin/users/{member.id}/status", json={"status": "deactivated"})
    assert res.status_code == 200 and res.json()["label"] == "Sam (deactivated)"
    assert m.get("/api/auth/me").status_code == 401  # session revoked
    bad = make_client().post("/api/auth/login", json={"email": member.email, "password": PASSWORD})
    assert bad.status_code == 403
    # Reactivate: can sign in again
    admin_client.patch(f"/api/admin/users/{member.id}/status", json={"status": "active"})
    assert (
        make_client().post("/api/auth/login", json={"email": member.email, "password": PASSWORD}).status_code
        == 200
    )


def test_change_password_signs_out_other_devices(admin, db) -> None:
    a, b = make_client(), make_client()
    sign_in(a, admin.email)
    sign_in(b, admin.email)
    res = a.post("/api/me/password", json={"current_password": PASSWORD, "new_password": "brand-new-pass-1"})
    assert res.status_code == 200
    assert b.get("/api/auth/me").status_code == 401
    assert a.get("/api/auth/me").status_code == 401  # own session too; sign in again with the new one
    assert sign_in(a, admin.email, "brand-new-pass-1").status_code == 200


def test_change_password_rejects_wrong_current_and_short_new(admin_client) -> None:
    assert (
        admin_client.post(
            "/api/me/password", json={"current_password": "x", "new_password": "long-enough-1"}
        ).status_code
        == 401
    )
    assert (
        admin_client.post(
            "/api/me/password", json={"current_password": PASSWORD, "new_password": "short"}
        ).status_code
        == 400
    )


# ---- invites -----------------------------------------------------------------------------------


def _invite_token(admin_client, **body) -> str:
    res = admin_client.post("/api/admin/invites", json={"role": "member", **body})
    assert res.status_code == 201, res.text
    url = res.json()["url"]
    # Links use the configured TRADING_PORTAL_ORIGINS (the test env sets http://localhost:5173), never
    # the request's Host; an Origin header that isn't configured is ignored too.
    assert url.startswith("http://localhost:5173/invite/")
    return url.rsplit("/", 1)[1]


def test_invite_link_ignores_a_spoofed_origin_header(admin_client) -> None:
    res = admin_client.post(
        "/api/admin/invites", json={"role": "member"}, headers={"Origin": "https://evil.example"}
    )
    assert res.status_code == 201 and res.json()["url"].startswith("http://localhost:5173/invite/")
    res = admin_client.post(
        "/api/admin/invites", json={"role": "member"}, headers={"Origin": "http://localhost:5173"}
    )
    assert res.json()["url"].startswith("http://localhost:5173/invite/")


def test_invite_flow_creates_member_and_signs_in(admin_client, db) -> None:
    token = _invite_token(admin_client)
    c = make_client()
    peek = c.get(f"/api/auth/invite/{token}")
    assert peek.status_code == 200 and peek.json()["role"] == "member"
    res = c.post(
        "/api/auth/invite/accept",
        json={"token": token, "email": "New@Example.test", "display_name": "Newbie", "password": PASSWORD},
    )
    assert res.status_code == 200, res.text
    assert res.json()["email"] == "new@example.test" and res.json()["role"] == "member"
    assert c.get("/api/auth/me").status_code == 200
    # tokens are stored hashed only
    from app.models import Invite

    inv = db.scalar(select(Invite))
    assert inv.token_hash == hash_token(token) and inv.used_at is not None


def test_invite_cannot_be_reused(admin_client) -> None:
    token = _invite_token(admin_client)
    body = {"token": token, "email": "one@example.test", "display_name": "One", "password": PASSWORD}
    assert make_client().post("/api/auth/invite/accept", json=body).status_code == 200
    body["email"] = "two@example.test"
    res = make_client().post("/api/auth/invite/accept", json=body)
    assert res.status_code == 410
    assert make_client().get(f"/api/auth/invite/{token}").status_code == 410


def test_expired_invite_is_rejected(admin_client, db) -> None:
    from app.models import Invite

    token = _invite_token(admin_client)
    inv = db.scalar(select(Invite))
    inv.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    res = make_client().post(
        "/api/auth/invite/accept",
        json={"token": token, "email": "late@example.test", "display_name": "Late", "password": PASSWORD},
    )
    assert res.status_code == 410 and "expired" in res.json()["detail"]


def test_invite_pinned_to_an_email_rejects_others(admin_client) -> None:
    token = _invite_token(admin_client, email="pinned@example.test")
    body = {"token": token, "email": "someone@example.test", "display_name": "X", "password": PASSWORD}
    assert make_client().post("/api/auth/invite/accept", json=body).status_code == 403


def test_bogus_invite_404(client) -> None:
    assert client.get("/api/auth/invite/not-a-token").status_code == 404


def test_member_cannot_create_invites(member_client) -> None:
    assert member_client.post("/api/admin/invites", json={"role": "member"}).status_code == 403


# ---- resets -------------------------------------------------------------------------------------


def test_admin_reset_link_is_one_time_and_one_hour(admin_client, member, db) -> None:
    res = admin_client.post(f"/api/admin/users/{member.id}/reset-link")
    assert res.status_code == 201
    token = res.json()["url"].rsplit("/", 1)[1]
    expires = res.json()["expires_at"]
    assert expires  # one hour: checked on the model
    from app.models import PasswordReset

    pr = db.scalar(select(PasswordReset))
    assert timedelta(minutes=59) < pr.expires_at - utcnow() <= timedelta(hours=1)

    c = make_client()
    ok = c.post("/api/auth/reset", json={"token": token, "password": "a-fresh-password-1"})
    assert ok.status_code == 200 and c.get("/api/auth/me").json()["email"] == member.email
    again = make_client().post("/api/auth/reset", json={"token": token, "password": "another-password-1"})
    assert again.status_code == 410
    assert sign_in(make_client(), member.email, "a-fresh-password-1").status_code == 200


def test_member_cannot_issue_reset_links(member_client, admin) -> None:
    assert member_client.post(f"/api/admin/users/{admin.id}/reset-link").status_code == 403


def test_owner_colour_indexes_cycle(db) -> None:
    users = [make_user(db, email=f"u{i}@example.test") for i in range(10)]
    assert [u.colour_index for u in users] == [0, 1, 2, 3, 4, 5, 6, 7, 0, 1]
