"""SQLite engine setup with integrity, contention, and lifecycle safeguards."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from dataset_foundry.persistence.models import Base

SessionFactory = sessionmaker[Session]


def _database_url(value: str | Path) -> tuple[str, bool]:
    raw = str(value)
    if "://" in raw:
        return raw, raw in {"sqlite://", "sqlite:///:memory:"}
    if raw == ":memory:":
        return "sqlite:///:memory:", True
    path = Path(raw)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return f"sqlite:///{path}", False


def _configure_sqlite_connection(dbapi_connection: object, _record: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
    finally:
        cursor.close()


class Database:
    """Own one engine and expose short, transactional session scopes."""

    def __init__(self, path_or_url: str | Path) -> None:
        url, in_memory = _database_url(path_or_url)
        engine_kwargs: dict[str, object] = {
            "connect_args": {"check_same_thread": False},
            "future": True,
        }
        if in_memory:
            engine_kwargs["poolclass"] = StaticPool
        self.engine: Engine = create_engine(url, **engine_kwargs)
        event.listen(self.engine, "connect", _configure_sqlite_connection)
        self.session_factory: SessionFactory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()


@contextmanager
def session_scope(session_factory: SessionFactory) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
