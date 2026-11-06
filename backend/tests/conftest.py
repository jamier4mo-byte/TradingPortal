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
# Tests never call Twelve Data, JBlanked or Forex Factory: blank every key a developer's .env may hold
# (environment variables win over .env), switch the feeds off and use the fake price provider.
os.environ["TRADING_PORTAL_FEEDS"] = "off"
os.environ["TRADING_PORTAL_PRICE_PROVIDER"] = "fake"
os.environ["TRADING_PORTAL_SCHEDULER"] = "false"
for _name in (
    "JBLANKED_API_KEY",
    "DEV_TWELVE_DATA_KEY",
    "VAPID_PUBLIC_KEY",
    "VAPID_PRIVATE_KEY",
    "VAPID_SUBJECT",
    # Screenshot storage stays local in tests; S3 tests build their own S3Storage inside moto.
    "STORAGE_BACKEND",
    "BUCKET_NAME",
    "AWS_ENDPOINT_URL_S3",
):
    os.environ[_name] = ""

BACKEND = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.api.auth import login_limiter  # noqa: E402
from app.core.deps import CSRF_COOKIE, CSRF_HEADER  # noqa: E402
from app.db import session_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    AlertDelivery,
    AlertPrefs,
    AppState,
    AuditLog,
    Event,
    EventType,
    FeedRun,
    Instrument,
    Invite,
    JournalSession,
    Lease,
    NewsHistoryCoverage,
    Passkey,
    PasswordReset,
    PriceCache,
    PriceCreditUsage,
    PricePin,
    PriceReaction,
    PushSubscription,
    Screenshot,
    Session,
    Strategy,
    Tag,
    Task,
    TaskCompletion,
    TaskException,
    Trade,
    User,
    UserApiKey,
    UserMarketPrefs,
    trade_tags,
)
from app.services import users as users_svc  # noqa: E402
from app.services.passkeys import challenges  # noqa: E402
from app.services.storage import get_storage  # noqa: E402


def _migration(name: str):
    spec = importlib.util.spec_from_file_location("seed", BACKEND / "migrations" / "versions" / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SEED_TAGS = _migration("0003_seed_tags.py").SEED_TAGS
SEED_INSTRUMENTS = _migration("0004_journal.py").SEED_INSTRUMENTS
FIXTURES = Path(__file__).parent / "fixtures"

PASSWORD = "correct-horse-battery"


@pytest.fixture(autouse=True)
def clean_db() -> Iterator[None]:
    """Each test starts with empty user tables and the seeded tags exactly as the migration left them."""
    yield
    with session_factory()() as db:
        db.execute(delete(trade_tags))
        # Prompt 4 tables. Seed tables (event_types marked seeded, news_instrument_map, price_symbols)
        # stay as the migrations left them; a test that edits one restores it itself.
        for model in (
            AlertDelivery,
            PushSubscription,
            AlertPrefs,
            PriceReaction,
            PriceCache,
            PriceCreditUsage,
            PricePin,
            UserMarketPrefs,
            Event,
            NewsHistoryCoverage,
            FeedRun,
            Lease,
            AppState,
        ):
            db.execute(delete(model))
        db.execute(delete(EventType).where(EventType.seeded.is_(False)))
        for model in (
            TaskCompletion,
            TaskException,
            Task,
            Screenshot,
            Trade,
            JournalSession,
            Strategy,
            Instrument,
            Tag,
            AuditLog,
            UserApiKey,
            Passkey,
            PasswordReset,
            Invite,
            Session,
            User,
        ):
            db.execute(delete(model))
        db.add_all(
            [
                Tag(name=n, slug=slug, category=c, synonyms=syn, status="approved")
                for n, slug, c, syn in SEED_TAGS
            ]
        )
        db.add_all(
            [
                Instrument(
                    symbol=sym,
                    name=name,
                    asset_class=cls,
                    pip_size=pip,
                    unit=unit,
                    price_decimals=dec,
                    aliases=al,
                )
                for sym, name, cls, pip, unit, dec, al in SEED_INSTRUMENTS
            ]
        )
        db.commit()
    storage = get_storage()
    if hasattr(storage, "wipe"):
        storage.wipe()
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
