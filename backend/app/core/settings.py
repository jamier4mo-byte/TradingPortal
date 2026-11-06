"""Settings, read from the environment and the repo-root `.env` (git-ignored).

Every variable is prefixed TRADING_PORTAL_, e.g. TRADING_PORTAL_SECRET_KEY.

  DATA_DIR     where the database (and later screenshots) live. Default ~/TradingPortal/data.
  SECRET_KEY   signs nothing directly but derives the Fernet key for the API-key vault.
               Production refuses to start without it. `make dev-secrets` writes one into .env.
  ENV          development (default) | production | test.
"""

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRADING_PORTAL_",
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["development", "production", "test"] = "development"
    data_dir: Path = Path("~/TradingPortal/data")
    secret_key: str | None = None

    # Sessions and sign-in
    session_days: int = 30
    session_slide_hours: int = 24  # extend the expiry at most this often
    lockout_threshold: int = 5
    lockout_minutes: int = 15
    login_rate_per_minute: int = 10  # per IP
    invite_days: int = 7
    reset_hours: int = 1

    # WebAuthn: the relying party is the site the app is served from.
    rp_id: str = "localhost"
    rp_name: str = "Trading Portal"
    origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])

    # ---- News Room, prices and alerts (Prompt 4) ----
    # feeds: live = call Forex Factory and JBlanked; off = never (tests, smoke, CI).
    feeds: Literal["live", "off"] = "live"
    # prices: auto = the user's vault key, else (development only) DEV_TWELVE_DATA_KEY, else the fake in
    # development; twelve_data = never fake; fake = never call Twelve Data (tests, smoke, CI).
    price_provider: Literal["auto", "twelve_data", "fake"] = "auto"
    # The in-app scheduler (an asyncio task started in the lifespan, single-instance by a DB lease).
    scheduler: bool = True
    scheduler_tick_seconds: int = 60
    ff_calendar_url: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    ff_min_interval_minutes: int = 60
    # JBlanked: never more than one request per interval, globally (a DB slot); plus a daily budget,
    # because the free tier allows one /calendar/today/ request a day (research, 6 Nov 2026).
    jblanked_min_interval_minutes: int = 5
    jblanked_daily_requests: int = 1
    jblanked_source: Literal["mql5", "forex-factory", "fxstreet"] = "forex-factory"
    # Unprefixed names: these are the names Jamie sets as Fly secrets / in .env.
    jblanked_api_key: str | None = Field(default=None, validation_alias="JBLANKED_API_KEY")
    dev_twelve_data_key: str | None = Field(default=None, validation_alias="DEV_TWELVE_DATA_KEY")
    vapid_public_key: str | None = Field(default=None, validation_alias="VAPID_PUBLIC_KEY")
    vapid_private_key: str | None = Field(default=None, validation_alias="VAPID_PRIVATE_KEY")
    vapid_subject: str | None = Field(default=None, validation_alias="VAPID_SUBJECT")

    @field_validator(
        "jblanked_api_key", "dev_twelve_data_key", "vapid_public_key", "vapid_private_key", "vapid_subject"
    )
    @classmethod
    def _blank_is_none(cls, v: str | None) -> str | None:
        return v.strip() or None if isinstance(v, str) else v

    @property
    def feeds_live(self) -> bool:
        return self.feeds == "live" and self.env != "test"

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.is_production

    @property
    def resolved_data_dir(self) -> Path:
        path = self.data_dir.expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.resolved_data_dir / 'portal.db'}"

    def require_secret_key(self) -> str:
        """The secret key, or a dev-only one persisted next to the database.

        Production never falls back: it refuses to start without TRADING_PORTAL_SECRET_KEY.
        """
        if self.secret_key:
            if self.is_production and len(self.secret_key) < 32:
                raise RuntimeError("TRADING_PORTAL_SECRET_KEY must be at least 32 characters in production.")
            return self.secret_key
        if self.is_production:
            raise RuntimeError(
                "TRADING_PORTAL_SECRET_KEY is not set. Set it as a Fly secret before starting in production."
            )
        dev_key = self.resolved_data_dir / ".dev-secret-key"
        if not dev_key.exists():
            dev_key.write_text(secrets.token_urlsafe(48))
            dev_key.chmod(0o600)
            log.warning(
                "No TRADING_PORTAL_SECRET_KEY; wrote a dev-only key to %s (run `make dev-secrets`).", dev_key
            )
        return dev_key.read_text().strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
