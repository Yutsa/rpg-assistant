from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from rpg_assistant.api.deps import get_db
from rpg_assistant.api.errors import not_found
from rpg_assistant.api.schemas import ChunkListItem, chunk_to_list_item
from rpg_assistant.models.raw import ChunkRecord
from rpg_assistant.storage.db import DatabaseConnection
from rpg_assistant.storage.repositories.raw import RawRepository

router = APIRouter(tags=["chunks"])


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkListItem])
def list_document_chunks(
    document_id: str,
    section_id: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    conn: DatabaseConnection = Depends(get_db),
) -> list[ChunkListItem]:
    chunks = RawRepository(conn).list_chunks(
        document_id,
        section_id=section_id,
        page_start=page_start,
        page_end=page_end,
        limit=limit,
        offset=offset,
    )
    return [chunk_to_list_item(c) for c in chunks]


@router.get("/chunks/{chunk_id}", response_model=ChunkRecord)
def get_chunk(
    chunk_id: str,
    conn: DatabaseConnection = Depends(get_db),
) -> ChunkRecord:
    chunk = RawRepository(conn).get_chunk(chunk_id)
    if not chunk:
        raise not_found("chunk", chunk_id)
    return chunk
