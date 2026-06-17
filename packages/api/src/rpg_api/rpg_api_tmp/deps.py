from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends

from rpg_assistant.api.errors import not_found
from rpg_assistant.storage.db import DatabaseConnection, get_connection
from rpg_assistant.storage.repositories.raw import RawRepository
from rpg_assistant.storage.repositories.semantic import SemanticRepository


def get_db() -> Generator[DatabaseConnection, None, None]:
    with get_connection() as conn:
        yield conn


def get_raw_repo(conn: DatabaseConnection = Depends(get_db)) -> RawRepository:
    return RawRepository(conn)


def get_semantic_repo(conn: DatabaseConnection = Depends(get_db)) -> SemanticRepository:
    return SemanticRepository(conn)


def require_document(repo: RawRepository, document_id: str) -> None:
    if repo.get_document(document_id) is None:
        raise not_found(f"Unknown document: {document_id}")
