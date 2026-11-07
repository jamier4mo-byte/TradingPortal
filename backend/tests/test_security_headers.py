"""Security headers, cache rules, the request-body cap, production-only switches and SPA path safety."""

import pytest

from app.core import headers as hdrs
from app.core.settings import Settings
from app.main import create_app
from tests.conftest import make_client

EXPECTED = {
    "referrer-policy": "strict-origin-when-cross-origin",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "cross-origin-opener-policy": "same-origin",
}


def _directives(csp: str) -> dict[str, str]:
    out = {}
    for part in csp.split(";"):
        name, _, value = part.strip().partition(" ")
        if name:
            out[name] = value
    return out


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(Settings, "is_production", property(lambda self: True))


def test_every_response_carries_the_headers(client, admin_client) -> None:
    for res in (client.get("/api/health"), client.get("/"), admin_client.get("/api/auth/me")):
        for name, value in EXPECTED.items():
            assert res.headers.get(name) == value, (res.url, name)
        assert "content-security-policy" in res.headers
    # Even a refused request (CSRF 403, 401) carries them: the middleware wraps everything.
    refused = client.request("POST", "/api/tags", json={}, no_csrf=True)
    assert refused.status_code == 403 and refused.headers["x-frame-options"] == "DENY"
    unauth = client.get("/api/auth/me")
    assert unauth.status_code == 401 and unauth.headers["x-content-type-options"] == "nosniff"


def test_csp_blocks_inline_script_and_framing(client) -> None:
    csp = _directives(client.get("/").headers["content-security-policy"])
    assert csp["script-src"] == "'self'"
    assert "'unsafe-inline'" not in csp["script-src"] and "'unsafe-eval'" not in csp["script-src"]
    assert csp["default-src"] == "'self'"
    assert csp["frame-ancestors"] == "'none'"
    assert csp["object-src"] == "'none'"
    assert csp["base-uri"] == "'self'"
    assert csp["form-action"] == "'self'"
    assert csp["worker-src"] == "'self' blob:"  # the Monte Carlo worker and the service worker
    assert csp["img-src"] == "'self' data: blob:"  # screenshot previews and ECharts canvases
    assert csp["style-src"] == "'self' 'unsafe-inline'"  # React/motion/FullCalendar style= attributes
    assert csp["font-src"] == "'self' data:"  # FullCalendar's icon font arrives as a data: URI
    assert "upgrade-insecure-requests" not in csp  # production only
    assert "strict-transport-security" not in client.get("/api/health").headers


def test_hsts_and_upgrade_only_in_production(client, production) -> None:
    res = client.get("/api/health")
    assert res.headers["strict-transport-security"] == "max-age=63072000; includeSubDomains"
    assert "upgrade-insecure-requests" in res.headers["content-security-policy"]


def test_cache_control_rules(client, admin_client) -> None:
    assert client.get("/api/auth/csrf").headers["cache-control"] == "no-store"
    assert admin_client.get("/api/auth/me").headers["cache-control"] == "no-store"
    assert admin_client.get("/api/me/keys").headers["cache-control"] == "no-store"
    assert admin_client.get("/api/admin/users").headers["cache-control"] == "no-store"
    assert client.get("/api/health").headers.get("cache-control") is None  # not one of the three prefixes
    assert hdrs.cache_control_for("/assets/index-abc123.js") == b"public, max-age=31536000, immutable"
    assert hdrs.cache_control_for("/sw.js") == b"no-cache"
    assert hdrs.cache_control_for("/index.html") == b"no-cache"
    assert hdrs.cache_control_for("/journal") is None  # the SPA handler sets no-cache itself
    assert hdrs.cache_control_for("/api/screenshots/1/full") is None  # the route sets private, immutable


def test_handlers_own_cache_control_wins(admin_client) -> None:
    res = admin_client.get("/api/admin/export")
    assert res.status_code == 200 and res.headers["cache-control"] == "no-store"
    assert res.headers["content-security-policy"]


# ---- body cap -------------------------------------------------------------------------------------------


def test_json_body_over_two_megabytes_is_refused_early(admin_client) -> None:
    big = {"name": "x" * (2 * 1024 * 1024 + 10), "category": "other"}
    res = admin_client.post("/api/tags", json=big)
    assert res.status_code == 413
    assert "2 MB" in res.json()["detail"]
    assert res.headers["x-frame-options"] == "DENY"


def test_chunked_body_over_the_cap_is_cut_off(admin_client) -> None:
    def chunks():
        for _ in range(3):
            yield b"x" * (1024 * 1024)

    res = admin_client.post("/api/tags", content=chunks(), headers={"Content-Type": "application/json"})
    assert res.status_code == 413


def test_upload_routes_have_their_own_larger_caps() -> None:
    assert hdrs.body_limit_for("/api/trades/7/screenshots") == 14 * 1024 * 1024
    assert hdrs.body_limit_for("/api/strategies/3/imports") == 6 * 1024 * 1024
    assert hdrs.body_limit_for("/api/strategies/3/imports/preview") == 6 * 1024 * 1024
    assert hdrs.body_limit_for("/api/tags") == 2 * 1024 * 1024
    assert hdrs.body_limit_for("/api/analytics/query") == 2 * 1024 * 1024


def test_small_bodies_and_gets_are_unaffected(admin_client) -> None:
    assert admin_client.get("/api/tags").status_code == 200
    assert admin_client.post("/api/tags", json={"name": "Small", "category": "other"}).status_code == 201


# ---- production switches ----------------------------------------------------------------------------------


def test_docs_schema_and_redoc_are_off_in_production(production) -> None:
    prod_app = create_app()
    paths = {getattr(r, "path", None) for r in prod_app.routes}
    assert not paths & {"/openapi.json", "/api/openapi.json", "/redoc", "/docs", "/api/docs"}


def test_docs_and_schema_available_outside_production(client) -> None:
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200
    assert b"redoc" not in client.get("/redoc").content.lower()  # never served (the SPA answers instead)


def test_credential_routes_never_echo_the_submitted_input(client, admin_client) -> None:
    res = client.post("/api/auth/login", json={"email": "jamie@example.test", "password": 12345})
    assert res.status_code == 422
    assert "12345" not in res.text and "input" not in res.text
    res = admin_client.post("/api/me/password", json={"current_password": 1, "new_password": "fresh-pass-1"})
    assert res.status_code == 422 and "input" not in res.text
    # Elsewhere the usual FastAPI shape (with `input`) stays, so forms can point at the bad field.
    res = admin_client.post("/api/tags", json={"name": 5, "category": "other"})
    assert res.status_code == 422 and "input" in res.text


# ---- SPA path handling -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/%2e%2e/%2e%2e/%2e%2e/etc/passwd",
        "/../../../etc/passwd",
        "/assets/../../backend/app/main.py",
        "//etc/passwd",
        "/%2fetc%2fpasswd",
    ],
)
def test_spa_never_serves_a_file_outside_dist(path) -> None:
    c = make_client()
    res = c.get(path)
    assert res.status_code in (200, 404)
    assert b"root:" not in res.content and b"create_app" not in res.content
    assert res.headers["content-type"].startswith(("text/html", "application/json"))


def test_api_404_is_json_not_the_spa(client) -> None:
    res = client.get("/api/no-such-thing")
    assert res.status_code == 404 and res.json() == {"detail": "Not Found"}
    res = client.get("/api/../index.html")
    assert res.headers["content-type"].startswith(("application/json", "text/html"))
