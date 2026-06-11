from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from rpg_assistant.api.deps import get_db
from rpg_assistant.api.errors import ambiguous_stat_block, not_found
from rpg_assistant.ingestion.raw.stat_blocks.serialize import chunk_to_stat_block_detail
from rpg_assistant.models.raw import StatBlockIndexEntry
from rpg_assistant.storage.db import DatabaseConnection
from rpg_assistant.storage.repositories.raw import RawRepository

router = APIRouter(tags=["stat-blocks"])


@router.get(
    "/documents/{document_id}/stat-blocks",
    response_model=list[StatBlockIndexEntry],
)
def list_document_stat_blocks(
    document_id: str,
    conn: DatabaseConnection = Depends(get_db),
) -> list[StatBlockIndexEntry]:
    return RawRepository(conn).list_stat_blocks(document_id)


@router.get("/documents/{document_id}/stat-blocks/{name}")
def get_document_stat_block(
    document_id: str,
    name: str,
    conn: DatabaseConnection = Depends(get_db),
) -> dict[str, Any]:
    result = RawRepository(conn).get_stat_block(document_id, name)
    if result is None:
        raise not_found("stat block", name)
    if isinstance(result, list):
        candidates = [
            {
                "name": (c.metadata.get("stat_block") or {}).get("name", ""),
                "nc": (c.metadata.get("stat_block") or {}).get("nc"),
                "chunk_id": c.id,
                "pages": {"start": c.page_start, "end": c.page_end},
            }
            for c in result
        ]
        raise ambiguous_stat_block(candidates)
    return chunk_to_stat_block_detail(result)
