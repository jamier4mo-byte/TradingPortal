"""Every /api route × every role, generated from the app itself, checked against a checked-in table.

The table below is the security contract: a route is `public` (no session needed), `member` (any signed-in
user; owner checks happen inside the handler) or `admin`. A new endpoint that isn't in the table fails
`test_every_route_is_classified` with a message telling you to add a row, so nothing ships unclassified.
Routes are discovered by walking the app's routers (that includes `include_in_schema=False` routes such
as /api/admin/export and the screenshot bytes), and the OpenAPI document is checked to be a subset.
"""

import pytest
from fastapi.routing import APIRoute

from app.api.auth import login_limiter
from app.main import app
from tests.conftest import make_client, sign_in

PUBLIC = "public"
MEMBER = "member"
ADMIN = "admin"

# (METHOD, path template) -> class. Keep sorted by path for easy diffs.
ROUTE_ROLES: dict[tuple[str, str], str] = {
    ("GET", "/api/admin/export"): ADMIN,
    ("POST", "/api/admin/invites"): ADMIN,
    ("GET", "/api/admin/users"): ADMIN,
    ("POST", "/api/admin/users/{user_id}/reset-link"): ADMIN,
    ("PATCH", "/api/admin/users/{user_id}/role"): ADMIN,
    ("PATCH", "/api/admin/users/{user_id}/status"): ADMIN,
    ("GET", "/api/alerts/config"): MEMBER,
    ("GET", "/api/alerts/devices"): MEMBER,
    ("GET", "/api/alerts/prefs"): MEMBER,
    ("PUT", "/api/alerts/prefs"): MEMBER,
    ("POST", "/api/alerts/subscriptions"): MEMBER,
    ("DELETE", "/api/alerts/subscriptions/{subscription_id}"): MEMBER,
    ("POST", "/api/alerts/test"): MEMBER,
    ("POST", "/api/analytics/copy"): MEMBER,
    ("GET", "/api/analytics/export/ai"): MEMBER,
    ("GET", "/api/analytics/export/csv"): MEMBER,
    ("POST", "/api/analytics/query"): MEMBER,
    ("GET", "/api/analytics/registry"): MEMBER,
    ("GET", "/api/auth/csrf"): PUBLIC,
    ("POST", "/api/auth/invite/accept"): PUBLIC,
    ("GET", "/api/auth/invite/{token}"): PUBLIC,
    ("POST", "/api/auth/login"): PUBLIC,
    ("POST", "/api/auth/logout"): PUBLIC,
    ("GET", "/api/auth/me"): MEMBER,
    ("POST", "/api/auth/passkey/login/begin"): PUBLIC,
    ("POST", "/api/auth/passkey/login/finish"): PUBLIC,
    ("POST", "/api/auth/reset"): PUBLIC,
    ("GET", "/api/calendar/occurrences"): MEMBER,
    ("GET", "/api/calendar/tasks"): MEMBER,
    ("POST", "/api/calendar/tasks"): MEMBER,
    ("DELETE", "/api/calendar/tasks/{task_id}"): MEMBER,
    ("GET", "/api/calendar/tasks/{task_id}"): MEMBER,
    ("PATCH", "/api/calendar/tasks/{task_id}"): MEMBER,
    ("DELETE", "/api/calendar/tasks/{task_id}/complete"): MEMBER,
    ("POST", "/api/calendar/tasks/{task_id}/complete"): MEMBER,
    ("GET", "/api/health"): PUBLIC,
    ("GET", "/api/hub"): MEMBER,
    ("GET", "/api/instruments"): MEMBER,
    ("POST", "/api/instruments"): ADMIN,
    ("PATCH", "/api/instruments/{instrument_id}"): ADMIN,
    ("DELETE", "/api/journal/sessions/{session_id}"): MEMBER,
    ("GET", "/api/journal/sessions/{session_id}"): MEMBER,
    ("PATCH", "/api/journal/sessions/{session_id}"): MEMBER,
    ("GET", "/api/journal/sessions/{session_id}/insights"): MEMBER,
    ("POST", "/api/journal/sessions/{session_id}/match"): MEMBER,
    ("POST", "/api/journal/sessions/{session_id}/restore"): MEMBER,
    ("GET", "/api/journal/sessions/{session_id}/trades"): MEMBER,
    ("GET", "/api/journal/summary"): MEMBER,
    ("GET", "/api/journal/trash"): MEMBER,
    ("PATCH", "/api/me"): MEMBER,
    ("GET", "/api/me/keys"): MEMBER,
    ("DELETE", "/api/me/keys/{provider}"): MEMBER,
    ("PUT", "/api/me/keys/{provider}"): MEMBER,
    ("POST", "/api/me/keys/{provider}/test"): MEMBER,
    ("GET", "/api/me/passkeys"): MEMBER,
    ("POST", "/api/me/passkeys/begin"): MEMBER,
    ("POST", "/api/me/passkeys/finish"): MEMBER,
    ("DELETE", "/api/me/passkeys/{passkey_id}"): MEMBER,
    ("POST", "/api/me/password"): MEMBER,
    ("GET", "/api/news/events"): MEMBER,
    ("GET", "/api/news/events/{event_id}"): MEMBER,
    ("GET", "/api/news/instrument-map"): MEMBER,
    ("PUT", "/api/news/instrument-map"): ADMIN,
    ("GET", "/api/news/next"): MEMBER,
    ("GET", "/api/news/prefs"): MEMBER,
    ("PATCH", "/api/news/prefs"): MEMBER,
    ("GET", "/api/news/status"): MEMBER,
    ("GET", "/api/news/timeline"): MEMBER,
    ("GET", "/api/news/today"): MEMBER,
    ("GET", "/api/news/week-ahead"): MEMBER,
    ("DELETE", "/api/prices/pins"): MEMBER,
    ("GET", "/api/prices/pins"): MEMBER,
    ("POST", "/api/prices/pins"): MEMBER,
    ("PUT", "/api/prices/pins/order"): MEMBER,
    ("GET", "/api/prices/quote"): MEMBER,
    ("GET", "/api/prices/quotes"): MEMBER,
    ("GET", "/api/prices/search"): MEMBER,
    ("PATCH", "/api/prices/settings"): MEMBER,
    ("GET", "/api/prices/sparkline"): MEMBER,
    ("GET", "/api/prices/usage"): MEMBER,
    ("DELETE", "/api/screenshots/{shot_id}"): MEMBER,
    ("PATCH", "/api/screenshots/{shot_id}"): MEMBER,
    ("GET", "/api/screenshots/{shot_id}/full"): MEMBER,
    ("GET", "/api/screenshots/{shot_id}/thumb"): MEMBER,
    ("GET", "/api/strategies"): MEMBER,
    ("POST", "/api/strategies"): MEMBER,
    ("DELETE", "/api/strategies/{strategy_id}"): MEMBER,
    ("GET", "/api/strategies/{strategy_id}"): MEMBER,
    ("PATCH", "/api/strategies/{strategy_id}"): MEMBER,
    ("GET", "/api/strategies/{strategy_id}/brief"): MEMBER,
    ("POST", "/api/strategies/{strategy_id}/imports"): MEMBER,
    ("POST", "/api/strategies/{strategy_id}/imports/preview"): MEMBER,
    ("GET", "/api/strategies/{strategy_id}/profile"): MEMBER,
    ("POST", "/api/strategies/{strategy_id}/restore"): MEMBER,
    ("GET", "/api/strategies/{strategy_id}/sessions"): MEMBER,
    ("POST", "/api/strategies/{strategy_id}/sessions"): MEMBER,
    ("GET", "/api/strategies/{strategy_id}/trades"): MEMBER,
    ("POST", "/api/strategies/{strategy_id}/trades"): MEMBER,
    ("GET", "/api/tags"): MEMBER,
    ("POST", "/api/tags"): MEMBER,  # members propose, admins create: same route
    ("GET", "/api/tags/resolve"): MEMBER,
    ("DELETE", "/api/tags/{tag_id}"): ADMIN,
    ("PATCH", "/api/tags/{tag_id}"): ADMIN,
    ("POST", "/api/tags/{tag_id}/merge"): ADMIN,
    ("DELETE", "/api/trades/{trade_id}"): MEMBER,
    ("GET", "/api/trades/{trade_id}"): MEMBER,
    ("PATCH", "/api/trades/{trade_id}"): MEMBER,
    ("POST", "/api/trades/{trade_id}/restore"): MEMBER,
    ("POST", "/api/trades/{trade_id}/screenshots"): MEMBER,
    ("GET", "/api/users"): MEMBER,
}

MULTIPART = {
    "/api/trades/{trade_id}/screenshots",
    "/api/strategies/{strategy_id}/imports",
    "/api/strategies/{strategy_id}/imports/preview",
}
CATCH_ALL = "/api/{path:path}"


def discover_routes() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()

    def walk(routes, prefix: str = "") -> None:
        for r in routes:
            if isinstance(r, APIRoute):
                path = prefix + r.path
                if path.startswith("/api/") and path != CATCH_ALL:
                    for m in r.methods - {"HEAD", "OPTIONS"}:
                        found.add((m, path))
            elif hasattr(r, "original_router"):
                # FastAPI ≥ 0.160 keeps included routers as wrappers whose routes still carry their own
                # (relative) paths; the include context holds the prefix they were mounted under.
                mounted = getattr(getattr(r, "include_context", None), "prefix", "") or ""
                walk(r.original_router.routes, prefix + mounted)
            elif hasattr(r, "routes"):
                walk(r.routes, prefix)

    walk(app.routes)
    return found


DISCOVERED = sorted(discover_routes())


def test_every_route_is_classified() -> None:
    unlisted = sorted(set(DISCOVERED) - set(ROUTE_ROLES))
    stale = sorted(set(ROUTE_ROLES) - set(DISCOVERED))
    assert not unlisted, (
        "New API routes without a row in tests/test_route_roles.py ROUTE_ROLES. Decide who may call each "
        f"(public | member | admin) and add it: {unlisted}"
    )
    assert not stale, f"ROUTE_ROLES lists routes that no longer exist: {stale}"


def test_openapi_is_a_subset_of_the_discovered_routes() -> None:
    schema = app.openapi()
    documented = {
        (method.upper(), path)
        for path, ops in schema["paths"].items()
        for method in ops
        if path.startswith("/api/")
    }
    assert documented <= set(DISCOVERED), documented - set(DISCOVERED)
    assert len(documented) >= 80


def _call(client, method: str, path: str):
    url = path
    for name in ("user_id", "token", "subscription_id", "task_id", "instrument_id", "session_id"):
        url = url.replace(f"{{{name}}}", "1")
    for name in ("provider", "passkey_id", "event_id", "shot_id", "strategy_id", "trade_id", "tag_id"):
        url = url.replace(f"{{{name}}}", "1")
    login_limiter.reset()  # the public routes share one per-IP limiter; this test isn't about it
    if method in ("POST", "PUT", "PATCH"):
        if path in MULTIPART:
            return client.request(method, url, files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
        return client.request(method, url, json={})
    return client.request(method, url)


@pytest.mark.parametrize("route", DISCOVERED, ids=lambda r: f"{r[0]} {r[1]}")
def test_role_gate(route, admin, member) -> None:
    method, path = route
    cls = ROUTE_ROLES.get(route)
    if cls is None:
        pytest.skip("unclassified: test_every_route_is_classified reports it")

    anon = _call(make_client(), method, path)
    as_member = make_client()
    sign_in(as_member, member.email)
    member_res = _call(as_member, method, path)
    as_admin = make_client()
    sign_in(as_admin, admin.email)
    admin_res = _call(as_admin, method, path)

    if cls == PUBLIC:
        assert anon.status_code not in (401, 403), f"anon on public {method} {path}: {anon.status_code}"
    else:
        assert anon.status_code == 401, f"anon {method} {path}: {anon.status_code} {anon.text}"
    assert admin_res.status_code not in (401, 403), f"admin {method} {path}: {admin_res.status_code}"
    if cls == ADMIN:
        assert member_res.status_code == 403, f"member {method} {path}: {member_res.status_code}"
    else:
        assert member_res.status_code not in (401, 403), f"member {method} {path}: {member_res.status_code}"
    for res in (anon, member_res, admin_res):
        # 503 is a deliberate "not configured" answer (push without VAPID keys); 500 would be a crash.
        assert res.status_code != 500, f"{method} {path}: {res.status_code} {res.text[:200]}"


def test_counts_per_class() -> None:
    """Documented in docs/build/SECURITY-REVIEW-5.md; update both when a route is added."""
    counts = {c: sum(1 for v in ROUTE_ROLES.values() if v == c) for c in (PUBLIC, MEMBER, ADMIN)}
    assert counts == {PUBLIC: 9, MEMBER: 89, ADMIN: 12}, counts
