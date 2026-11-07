"""Per-IP limits on the unauthenticated routes and the per-user budget on the expensive endpoints."""

import io
import zipfile

import pytest

from app.api.auth import login_limiter
from app.core.deps import heavy_limiter
from app.services.fxreplay import MAX_CSV_ROWS, CsvFormatError, parse_csv
from tests.conftest import make_client

PUBLIC_POSTS = [
    ("POST", "/api/auth/login", {"email": "x@example.test", "password": "whatever-123"}),
    (
        "POST",
        "/api/auth/invite/accept",
        {"token": "t", "email": "a@b.c", "display_name": "A", "password": "p" * 12},
    ),
    ("POST", "/api/auth/reset", {"token": "t", "password": "p" * 12}),
    ("POST", "/api/auth/passkey/login/begin", None),
    ("POST", "/api/auth/passkey/login/finish", {"challenge_key": "k", "credential": {}}),
    ("GET", "/api/auth/invite/not-a-token", None),
]


@pytest.mark.parametrize("case", PUBLIC_POSTS, ids=lambda c: f"{c[0]} {c[1]}")
def test_every_unauthenticated_auth_route_is_rate_limited_per_ip(case) -> None:
    method, path, body = case
    login_limiter.reset()
    client = make_client()
    for _ in range(login_limiter.limit):
        res = client.request(method, path, json=body)
        assert res.status_code != 429
    assert client.request(method, path, json=body).status_code == 429


def test_heavy_endpoints_share_a_per_user_budget(admin_client, member_client) -> None:
    for _ in range(heavy_limiter.limit):
        assert admin_client.get("/api/analytics/export/csv").status_code == 200
    assert admin_client.get("/api/analytics/export/csv").status_code == 429
    assert admin_client.get("/api/analytics/export/ai").status_code == 429
    assert admin_client.get("/api/admin/export").status_code == 429
    # Per user: the member's budget is separate, and ordinary routes are unaffected.
    assert member_client.get("/api/analytics/export/csv").status_code == 200
    assert admin_client.get("/api/strategies").status_code == 200


def test_import_preview_counts_against_the_budget(admin_client) -> None:
    from tests.test_journal_api import SAMPLE, new_strategy

    s = new_strategy(admin_client)
    for _ in range(heavy_limiter.limit):
        res = admin_client.post(
            f"/api/strategies/{s['id']}/imports/preview", files={"file": ("x.csv", SAMPLE, "text/csv")}
        )
        assert res.status_code == 200, res.text
    res = admin_client.post(
        f"/api/strategies/{s['id']}/imports/preview", files={"file": ("x.csv", SAMPLE, "text/csv")}
    )
    assert res.status_code == 429


def test_csv_import_caps_bytes_and_rows(admin_client) -> None:
    from tests.test_journal_api import SAMPLE, new_strategy

    header = SAMPLE.split(b"\n", 1)[0]
    with pytest.raises(CsvFormatError, match="rows"):
        parse_csv(header + b"\n" + b"1,2\n" * (MAX_CSV_ROWS + 1))
    with pytest.raises(CsvFormatError, match="5 MB"):
        parse_csv(b"x" * (5 * 1024 * 1024 + 1))
    # Over the wire the body middleware answers 413 before the route reads the file.
    s = new_strategy(admin_client)
    big = io.BytesIO(b"a,b\n" + b"1,2\n" * (2 * 1024 * 1024))
    res = admin_client.post(
        f"/api/strategies/{s['id']}/imports/preview", files={"file": ("big.csv", big.getvalue(), "text/csv")}
    )
    assert res.status_code == 413


def test_export_still_a_zip_within_budget(admin_client) -> None:
    res = admin_client.get("/api/analytics/export/ai")
    assert res.status_code == 200 and zipfile.ZipFile(io.BytesIO(res.content)).testzip() is None
