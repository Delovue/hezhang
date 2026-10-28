from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool


def build_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise ValueError("Use a file-based SQLite database")
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 5},
        poolclass=NullPool,
        hide_parameters=True,
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    @event.listens_for(engine, "begin")
    def begin_sqlite(connection):
        mode = connection.get_execution_options().get("transaction_mode", "DEFERRED")
        if mode not in {"DEFERRED", "IMMEDIATE"}:
            raise ValueError("Unsupported transaction mode")
        connection.exec_driver_sql(f"BEGIN {mode}")

    return engine


@contextmanager
def transaction(engine: Engine, *, write: bool = False) -> Iterator[Session]:
    # Lock before reading permissions, activity status or expense version.
    bind = engine.execution_options(transaction_mode="IMMEDIATE" if write else "DEFERRED")
    with Session(bind, expire_on_commit=False) as session, session.begin():
        yield session
