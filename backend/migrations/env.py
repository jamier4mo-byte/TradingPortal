from alembic import context

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.db import Base, get_engine

target_metadata = Base.metadata


def run() -> None:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run()
