"""Command line: `python -m app.cli <command>`.

create-admin   ask for email and password and create the first admin (also via `fly ssh console`)
seed-dev       fill the data dir with an admin, two members and sample records (dev only)
migrate        alembic upgrade head
"""

import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path

from .core.settings import get_settings
from .db import session_factory
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
        print(
            "Seeded /tmp-style dev data:\n"
            "  admin   jamie@example.test / password-dev-1\n"
            "  member  sam@example.test   / password-dev-1  (has a Twelve Data key saved)\n"
            "  member  alex@example.test  / password-dev-1\n"
            "  plus two proposed tags and one open invite"
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-admin")
    p.add_argument("--email")
    p.add_argument("--name")
    p.add_argument("--password-env", help="read the password from this environment variable (scripts only)")
    sub.add_parser("seed-dev")
    sub.add_parser("migrate")
    args = parser.parse_args(argv)
    if args.command == "create-admin":
        create_admin(args.email, os.environ.get(args.password_env) if args.password_env else None, args.name)
    elif args.command == "seed-dev":
        seed_dev()
    elif args.command == "migrate":
        migrate()


if __name__ == "__main__":
    main()
