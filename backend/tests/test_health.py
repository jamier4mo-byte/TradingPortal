import os
import tempfile

os.environ.setdefault("TRADING_PORTAL_DATA_DIR", tempfile.mkdtemp(prefix="tp-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_health() -> None:
    body = TestClient(app).get("/api/health").json()
    assert body["app"] == "Trading Portal"
    assert body["db_ok"] is True


def test_unknown_api_path_is_not_the_spa() -> None:
    assert TestClient(app).get("/api/nope").json() == {"detail": "Not Found"}
