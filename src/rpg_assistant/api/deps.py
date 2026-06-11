from __future__ import annotations

from collections.abc import Generator

from rpg_assistant.storage.db import DatabaseConnection, get_connection


def get_db() -> Generator[DatabaseConnection, None, None]:
    with get_connection() as conn:
        yield conn
