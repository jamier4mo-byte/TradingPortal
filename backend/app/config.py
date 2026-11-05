"""Settings, read once from the environment.

TRADING_PORTAL_DATA_DIR  where the database (and later screenshots) live.
                         Default ~/TradingPortal/data. Never inside the repo.
"""

import os
from pathlib import Path


def data_dir() -> Path:
    raw = os.environ.get("TRADING_PORTAL_DATA_DIR") or "~/TradingPortal/data"
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_url() -> str:
    return f"sqlite:///{data_dir() / 'portal.db'}"


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
