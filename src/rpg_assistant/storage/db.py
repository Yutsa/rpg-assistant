from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Generator, Protocol

import psycopg
from sqlalchemy.engine import make_url

from rpg_assistant.storage.dialect import (
    DEFAULT_SQLITE_URL,
    Dialect,
    detect_dialect,
    get_database_url_from_env,
)


def _adapt_sqlite_datetime(val: datetime) -> str:
    return val.isoformat(" ")


def _adapt_sqlite_date(val: date) -> str:
    return val.isoformat()


def _register_sqlite_datetime_adapters() -> None:
    sqlite3.register_adapter(datetime, _adapt_sqlite_datetime)
    sqlite3.register_adapter(date, _adapt_sqlite_date)


_register_sqlite_datetime_adapters()


class DatabaseConnection(Protocol):
    dialect: Dialect

    def cursor(self) -> Any: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class _SqliteCursor:
    def __init__(self, cursor: sqlite3.Cursor) -> None:
        self._cursor = cursor

    def execute(self, query: str, params: Any = None) -> "_SqliteCursor":
        self._cursor.execute(query.replace("%s", "?"), params or ())
        return self

    def executemany(self, query: str, params_seq: Any) -> "_SqliteCursor":
        self._cursor.executemany(query.replace("%s", "?"), params_seq)
        return self

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cursor.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def __enter__(self) -> "_SqliteCursor":
        return self

    def __exit__(self, *args: Any) -> None:
        self._cursor.close()


class _SqliteConnection:
    def __init__(self, connection: sqlite3.Connection, dialect: Dialect) -> None:
        self._connection = connection
        self.dialect = dialect

    def cursor(self) -> _SqliteCursor:
        return _SqliteCursor(self._connection.cursor())

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()


class _PostgresConnection:
    def __init__(self, connection: psycopg.Connection, dialect: Dialect) -> None:
        self._connection = connection
        self.dialect = dialect

    def cursor(self) -> Any:
        return self._connection.cursor()

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()


def resolve_database_url(env_value: str | None) -> str:
    raw = get_database_url_from_env(env_value)
    url = raw
    if "${workspaceFolder}" in url:
        url = DEFAULT_SQLITE_URL
    if detect_dialect(url) == "sqlite":
        db_path = Path(_sqlite_database_path(url))
        if not db_path.is_absolute():
            db_path = (Path.cwd() / db_path).resolve()
            url = f"sqlite:///{db_path.as_posix()}"
    return url


def get_database_url() -> str:
    return resolve_database_url(os.environ.get("DATABASE_URL"))


def get_dialect(database_url: str | None = None) -> Dialect:
    url = database_url or get_database_url()
    return Dialect(detect_dialect(url))


def _sqlite_database_path(database_url: str) -> str:
    parsed = make_url(database_url)
    if parsed.database is None:
        raise ValueError(f"Invalid SQLite URL: {database_url}")
    return parsed.database


def _open_connection(database_url: str) -> DatabaseConnection:
    dialect = Dialect(detect_dialect(database_url))
    if dialect.is_sqlite:
        db_path = _sqlite_database_path(database_url)
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return _SqliteConnection(connection, dialect)

    connection = psycopg.connect(database_url)
    return _PostgresConnection(connection, dialect)


@contextmanager
def get_connection() -> Generator[DatabaseConnection, None, None]:
    conn = _open_connection(get_database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if isinstance(conn, _SqliteConnection):
            conn._connection.close()
        elif isinstance(conn, _PostgresConnection):
            conn._connection.close()
