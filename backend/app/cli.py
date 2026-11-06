"""Command line: `python -m app.cli <command>`.

create-admin   ask for email and password and create the first admin (also via `fly ssh console`)
seed-dev       fill the data dir with an admin, two members and sample records (dev only)
migrate        alembic upgrade head
news-backfill  load JBlanked event history month by month (resumable; respects the API limits)
"""

import argparse
import getpass
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from .core.settings import get_settings
from .db import session_factory
from .services import journal as journal_svc
from .services import keys as keys_svc
from .services import tags as tags_svc
from .services import users as users_svc
from .services.users import AuthError

BACKEND = Path(__file__).resolve().parents[1]


def migrate() -> None:
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True)


def create_admin(email: str | None = None, password: str | None = None, name: str | None = None) -> None:
    migrate()
    email = email or input("Admin email: ").strip()
    name = name or input("Display name [Jamie]: ").strip() or "Jamie"
    if not password:
        password = getpass.getpass("Password (10+ chars): ")
        if password != getpass.getpass("Again: "):
            sys.exit("Passwords don't match.")
    with session_factory()() as db:
        try:
            user = users_svc.create_user(db, email=email, display_name=name, password=password, role="admin")
        except AuthError as exc:
            sys.exit(exc.message)
        db.commit()
        print(f"Admin created: {user.email} (id {user.id}). Sign in at the login page.")


def seed_dev() -> None:
    settings = get_settings()
    if settings.is_production:
        sys.exit("seed-dev never runs in production.")
    migrate()
    with session_factory()() as db:
        if users_svc.list_users(db):
            print(f"{settings.resolved_data_dir} already has users; nothing seeded.")
            return
        admin = users_svc.create_user(
            db, email="jamie@example.test", display_name="Jamie", password="password-dev-1", role="admin"
        )
        sam = users_svc.create_user(
            db, email="sam@example.test", display_name="Sam", password="password-dev-1"
        )
        alex = users_svc.create_user(
            db, email="alex@example.test", display_name="Alex", password="password-dev-1"
        )
        db.commit()
        keys_svc.set_key(db, sam, "twelve_data", "demo-key-not-real-1234")
        tags_svc.propose_tag(db, alex, name="Rejection block", category="pd_array", synonyms=["RB"])
        tags_svc.propose_tag(
            db, sam, name="Consequent encroachment", category="pd_array", synonyms=["CE", "50% of FVG"]
        )
        users_svc.create_invite(db, admin, role="member")
        _seed_journal(db, admin, sam)
        _seed_news(db)
        print(
            "Seeded /tmp-style dev data:\n"
            "  admin   jamie@example.test / password-dev-1\n"
            "  member  sam@example.test   / password-dev-1  (has a Twelve Data key saved)\n"
            "  member  alex@example.test  / password-dev-1\n"
            "  plus two proposed tags, one open invite, two strategies with imported trades and a\n"
            "  synthetic news week (with a year of US CPI and NFP history and price reactions)"
        )


def _seed_journal(db, admin, sam) -> None:
    """A strategy each, with the synthetic FX Replay fixture imported, so the journal screens have data."""
    fixture = BACKEND / "tests" / "fixtures" / "fxreplay-sample.csv"
    if not fixture.exists():
        return
    data = fixture.read_bytes()
    strategy = journal_svc.create_strategy(
        db,
        admin,
        name="NAS100 silver bullet",
        description="10:00–11:00 New York FVG entries after a liquidity sweep.",
        instruments=["NAS100"],
        timeframes=["5m", "1m"],
        entry_models=["FVG", "Breaker"],
    )
    journal_svc.confirm_import(db, admin, strategy, data, destination="ideal", filename="fxreplay-sample.csv")
    journal_svc.confirm_import(
        db, admin, strategy, data, destination="backtest", filename="fxreplay-sample.csv"
    )
    other = journal_svc.create_strategy(
        db,
        sam,
        name="EURUSD London reversal",
        instruments=["EURUSD"],
        timeframes=["15m"],
        entry_models=["OTE"],
    )
    journal_svc.confirm_import(db, sam, other, data, destination="ideal", filename="fxreplay-sample.csv")
    _seed_analytics(db, admin, sam)


def _seed_analytics(db, admin, sam) -> None:
    """Synthetic trades (deterministic) so the Analytics, Compare and Export screens have something to show.

    Strategy 3 (Jamie): 7 months of ideal winners (unlocked) and 160 backtest trades. Strategy 4 (Sam): 80
    backtest trades, so the all-strategies view can split by owner. Dev data only: /tmp/tp-dev.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select

    from .models import Trade, User
    from .services.analytics.synthetic import insert_trades, trade_dicts

    alex = db.scalar(select(User).where(User.email == "alex@example.test"))
    mine = journal_svc.create_strategy(
        db,
        admin,
        name="NAS100 London breaker",
        description="London-open sweep of Asia's range, then a breaker or FVG entry towards the daily draw.",
        instruments=["NAS100"],
        timeframes=["15m", "5m"],
        entry_models=["FVG", "Breaker", "OTE", "Order block"],
    )
    rows: list[dict] = []
    for month in range(7):
        start = datetime(2025, 3 + month, 3, 7, 0, tzinfo=UTC)
        rows += trade_dicts(mine, admin.id, 5, kind="ideal", seed=100 + month, start=start)
    rows += trade_dicts(
        mine, admin.id, 160, kind="backtest", seed=11, start=datetime(2025, 10, 6, 7, tzinfo=UTC)
    )
    insert_trades(db, rows)
    sams = journal_svc.create_strategy(
        db,
        sam,
        name="NAS100 New York reversal",
        instruments=["NAS100"],
        timeframes=["5m"],
        entry_models=["OTE"],
    )
    insert_trades(db, trade_dicts(sams, sam.id, 80, seed=21, start=datetime(2025, 10, 6, 13, tzinfo=UTC)))
    if alex:
        alexs = journal_svc.create_strategy(
            db,
            alex,
            name="NAS100 Asia range",
            instruments=["NAS100"],
            timeframes=["15m"],
            entry_models=["FVG"],
        )
        insert_trades(
            db, trade_dicts(alexs, alex.id, 40, seed=31, start=datetime(2025, 11, 3, 1, tzinfo=UTC))
        )
    names = [
        t for t in (tags_svc.resolve_tag(db, n) for n in ("FVG", "Liquidity sweep", "London killzone")) if t
    ]
    for i, trade in enumerate(
        db.scalars(select(Trade).where(Trade.strategy_id == mine.id).order_by(Trade.id))
    ):
        if names and i % 3 == 0:
            trade.tags = names[: 1 + i % len(names)]
    db.commit()


def _seed_news(db) -> None:
    """Synthetic news around now (dev only), then tag every seeded trade."""
    from .models import utcnow
    from .services.news import synthetic, tagging

    synthetic.seed(db, utcnow())
    tagging.retag(db)


def news_backfill(start: str | None, max_requests: int | None) -> None:
    from .services.news import backfill

    migrate()
    first = date.fromisoformat(start) if start else None
    with session_factory()() as db:
        out = backfill.run(db, start=first, max_requests=max_requests)
    if out["status"] in ("not_configured", "refused", "error"):
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-admin")
    p.add_argument("--email")
    p.add_argument("--name")
    p.add_argument("--password-env", help="read the password from this environment variable (scripts only)")
    sub.add_parser("seed-dev")
    sub.add_parser("migrate")
    p = sub.add_parser("news-backfill")
    p.add_argument("--from", dest="start", help="first date to load, YYYY-MM-DD (default 2023-01-01)")
    p.add_argument("--max-requests", type=int, help="stop after N requests (default: the daily budget)")
    args = parser.parse_args(argv)
    if args.command == "create-admin":
        create_admin(args.email, os.environ.get(args.password_env) if args.password_env else None, args.name)
    elif args.command == "seed-dev":
        seed_dev()
    elif args.command == "migrate":
        migrate()
    elif args.command == "news-backfill":
        news_backfill(args.start, args.max_requests)


if __name__ == "__main__":
    main()
