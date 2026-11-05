"""Database engine and session. Schema changes go through Alembic (backend/migrations)."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .core.settings import get_settings
from .models.base import Base

__all__ = ["Base", "get_engine", "get_session", "session_factory"]


@lru_cache
def get_engine() -> Engine:
    engine = create_engine(get_settings().database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@lru_cache
def session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with session_factory()() as session:
        yield session
