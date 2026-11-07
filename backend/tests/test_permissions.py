"""Role × action matrix: members change only their own records, admins anything, deactivated users nothing."""

from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.deps import apply_scope, require_owner_or_admin
from app.models import UserApiKey
from tests.conftest import make_client, sign_in

# (method, path, body) -> {role: expected status}. `{id}` is filled with the *member's* id.
MATRIX = [
    ("GET", "/api/auth/me", None, {"admin": 200, "member": 200, "anon": 401}),
    ("GET", "/api/users", None, {"admin": 200, "member": 200, "anon": 401}),
    ("GET", "/api/admin/users", None, {"admin": 200, "member": 403, "anon": 401}),
    ("GET", "/api/hub", None, {"admin": 200, "member": 200, "anon": 401}),
    ("POST", "/api/admin/invites", {"role": "member"}, {"admin": 201, "member": 403, "anon": 401}),
    ("PATCH", "/api/admin/users/{id}/role", {"role": "admin"}, {"admin": 200, "member": 403, "anon": 401}),
    (
        "PATCH",
        "/api/admin/users/{id}/status",
        {"status": "active"},
        {"admin": 200, "member": 403, "anon": 401},
    ),
    ("POST", "/api/admin/users/{id}/reset-link", None, {"admin": 201, "member": 403, "anon": 401}),
    ("GET", "/api/tags", None, {"admin": 200, "member": 200, "anon": 401}),
    (
        "POST",
        "/api/tags",
        {"name": "Zz tag", "category": "other"},
        {"admin": 201, "member": 201, "anon": 401},
    ),
    ("PATCH", "/api/tags/1", {"name": "FVG"}, {"admin": 200, "member": 403, "anon": 401}),
    ("POST", "/api/tags/1/merge", {"into_id": 2}, {"admin": 200, "member": 403, "anon": 401}),
    ("DELETE", "/api/tags/3", None, {"admin": 200, "member": 403, "anon": 401}),
    ("GET", "/api/me/keys", None, {"admin": 200, "member": 200, "anon": 401}),
    ("PUT", "/api/me/keys/twelve_data", {"key": "abcdefgh1234"}, {"admin": 200, "member": 200, "anon": 401}),
    ("PATCH", "/api/me", {"motion_pref": "reduced"}, {"admin": 200, "member": 200, "anon": 401}),
    ("GET", "/api/calendar/occurrences", None, {"admin": 200, "member": 200, "anon": 401}),
    ("GET", "/api/calendar/tasks", None, {"admin": 200, "member": 200, "anon": 401}),
    (
        "POST",
        "/api/calendar/tasks",
        {"title": "Backtest session", "start_at": "2026-11-09T09:00:00Z"},
        {"admin": 201, "member": 201, "anon": 401},
    ),
    ("GET", "/api/admin/export", None, {"admin": 200, "member": 403, "anon": 401}),
]


def _ids(case):
    method, path, _, _ = case
    return f"{method} {path}"


@pytest.mark.parametrize("case", MATRIX, ids=_ids)
@pytest.mark.parametrize("role", ["admin", "member", "anon"])
def test_role_matrix(case, role, admin, member) -> None:
    method, path, body, expected = case
    path = path.replace("{id}", str(member.id))
    c = make_client()
    if role == "admin":
        sign_in(c, admin.email)
    elif role == "member":
        sign_in(c, member.email)
    res = c.request(method, path, json=body)
    assert res.status_code == expected[role], f"{role} {method} {path}: {res.status_code} {res.text}"


def test_deactivated_user_can_do_nothing(admin_client, member) -> None:
    m = make_client()
    sign_in(m, member.email)
    admin_client.patch(f"/api/admin/users/{member.id}/status", json={"status": "deactivated"})
    for method, path, body in [
        ("GET", "/api/auth/me", None),
        ("GET", "/api/tags", None),
        ("POST", "/api/tags", {"name": "Nope", "category": "other"}),
        ("PUT", "/api/me/keys/twelve_data", {"key": "abcdefgh1234"}),
        ("PATCH", "/api/me", {"display_name": "Ghost"}),
    ]:
        assert m.request(method, path, json=body).status_code in (401, 403), f"{method} {path}"


def test_admin_cannot_demote_or_deactivate_self(admin_client, admin) -> None:
    assert admin_client.patch(f"/api/admin/users/{admin.id}/role", json={"role": "member"}).status_code == 409
    r = admin_client.patch(f"/api/admin/users/{admin.id}/status", json={"status": "deactivated"})
    assert r.status_code == 409


def test_admin_can_promote_and_demote_a_member(admin_client, member) -> None:
    assert (
        admin_client.patch(f"/api/admin/users/{member.id}/role", json={"role": "admin"}).json()["role"]
        == "admin"
    )
    assert (
        admin_client.patch(f"/api/admin/users/{member.id}/role", json={"role": "member"}).json()["role"]
        == "member"
    )


def test_deactivated_users_stay_listed_with_label(admin_client, member) -> None:
    admin_client.patch(f"/api/admin/users/{member.id}/status", json={"status": "deactivated"})
    users = admin_client.get("/api/users").json()
    sam = next(u for u in users if u["id"] == member.id)
    assert sam["label"] == "Sam (deactivated)" and sam["status"] == "deactivated"


# ---- helper semantics ---------------------------------------------------------------------------------


@dataclass
class Owned:
    owner_id: int


def test_require_owner_or_admin(admin, member, other_member) -> None:
    require_owner_or_admin(Owned(owner_id=member.id), member)  # own record: fine
    require_owner_or_admin(Owned(owner_id=member.id), admin)  # admin: anything
    with pytest.raises(HTTPException) as exc:
        require_owner_or_admin(Owned(owner_id=member.id), other_member)
    assert exc.value.status_code == 403


def test_scope_filter_mine_everyone_others(db, admin, member, other_member) -> None:
    from app.services import keys as keys_svc

    for u in (admin, member, other_member):
        keys_svc.set_key(db, u, "twelve_data", f"key-for-{u.email}")
    base = select(UserApiKey.owner_id)
    mine = set(db.scalars(apply_scope(base, UserApiKey.owner_id, "mine", member)))
    others = set(db.scalars(apply_scope(base, UserApiKey.owner_id, "others", member)))
    everyone = set(db.scalars(apply_scope(base, UserApiKey.owner_id, "everyone", member)))
    assert mine == {member.id}
    assert others == {admin.id, other_member.id}
    assert everyone == {admin.id, member.id, other_member.id}
