"""Test fixtures: one throw-away data dir per session with migrations applied; clean tables per test.

Environment is fixed before the app is imported so nothing from a developer's .env leaks in.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

DATA_DIR = Path(tempfile.mkdtemp(prefix="tp-test-"))
os.environ["TRADING_PORTAL_ENV"] = "test"
os.environ["TRADING_PORTAL_DATA_DIR"] = str(DATA_DIR)
os.environ["TRADING_PORTAL_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-anything-0123456789"
os.environ["TRADING_PORTAL_RP_ID"] = "localhost"
os.environ["TRADING_PORTAL_ORIGINS"] = '["http://localhost:5173"]'

BACKEND = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.api.auth import login_limiter  # noqa: E402
from app.core.deps import CSRF_COOKIE, CSRF_HEADER  # noqa: E402
from app.db import session_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AuditLog, Invite, Passkey, PasswordReset, Session, Tag, User, UserApiKey  # noqa: E402
from app.services import users as users_svc  # noqa: E402
from app.services.passkeys import challenges  # noqa: E402


def _seed_tags() -> list[tuple[str, str, str, list[str]]]:
    spec = importlib.util.spec_from_file_location(
        "seed", BACKEND / "migrations" / "versions" / "0003_seed_tags.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SEED_TAGS


SEED_TAGS = _seed_tags()

PASSWORD = "correct-horse-battery"


@pytest.fixture(autouse=True)
def clean_db() -> Iterator[None]:
    """Each test starts with empty user tables and the seeded tags exactly as the migration left them."""
    yield
    with session_factory()() as db:
        for model in (Tag, AuditLog, UserApiKey, Passkey, PasswordReset, Invite, Session, User):
            db.execute(delete(model))
        db.add_all(
            [
                Tag(name=n, slug=slug, category=c, synonyms=syn, status="approved")
                for n, slug, c, syn in SEED_TAGS
            ]
        )
        db.commit()
    login_limiter.reset()
    challenges.clear()


@pytest.fixture
def db():
    with session_factory()() as session:
        yield session


class Client(TestClient):
    """TestClient that sends the CSRF header automatically once it holds the cookie."""

    def request(self, method, url, **kwargs):  # type: ignore[override]
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"} and not kwargs.pop("no_csrf", False):
            token = self.cookies.get(CSRF_COOKIE)
            if token is None:
                super().request("GET", "/api/auth/csrf")
                token = self.cookies.get(CSRF_COOKIE)
            headers = dict(kwargs.pop("headers", None) or {})
            headers.setdefault(CSRF_HEADER, token or "")
            kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


def make_client() -> Client:
    return Client(app, base_url="http://localhost")


@pytest.fixture
def client() -> Client:
    return make_client()


def make_user(
    db, *, email: str, role: str = "member", name: str | None = None, password: str = PASSWORD
) -> User:
    user = users_svc.create_user(
        db, email=email, display_name=name or email.split("@")[0].title(), password=password, role=role
    )
    db.commit()
    return user


@pytest.fixture
def admin(db) -> User:
    return make_user(db, email="jamie@example.test", role="admin", name="Jamie")


@pytest.fixture
def member(db) -> User:
    return make_user(db, email="sam@example.test", name="Sam")


@pytest.fixture
def other_member(db) -> User:
    return make_user(db, email="alex@example.test", name="Alex")


def sign_in(client: Client, email: str, password: str = PASSWORD):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res


@pytest.fixture
def admin_client(admin) -> Client:
    c = make_client()
    sign_in(c, admin.email)
    return c


@pytest.fixture
def member_client(member) -> Client:
    c = make_client()
    sign_in(c, member.email)
    return c
