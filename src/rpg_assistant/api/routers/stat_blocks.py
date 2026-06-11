from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from rpg_assistant.api.deps import get_raw_repo
from rpg_assistant.api.errors import ambiguous_stat_block, not_found
from rpg_assistant.api.schemas import StatBlockIndexOut
from rpg_assistant.ingestion.raw.stat_blocks.serialize import chunk_to_stat_block_detail
from rpg_assistant.storage.repositories.raw import RawRepository

router = APIRouter(prefix="/documents", tags=["stat-blocks"])


def _require_document(repo: RawRepository, document_id: str) -> None:
    if repo.get_document(document_id) is None:
        raise not_found(f"Unknown document: {document_id}")


@router.get("/{document_id}/stat-blocks", response_model=list[StatBlockIndexOut])
def list_stat_blocks(
    document_id: str,
    repo: RawRepository = Depends(get_raw_repo),
) -> list[StatBlockIndexOut]:
    _require_document(repo, document_id)
    return [
        StatBlockIndexOut(**entry.model_dump())
        for entry in repo.list_stat_blocks(document_id)
    ]


@router.get("/{document_id}/stat-blocks/{name}", response_model=None)
def get_stat_block(
    document_id: str,
    name: str,
    repo: RawRepository = Depends(get_raw_repo),
) -> dict[str, Any] | JSONResponse:
    _require_document(repo, document_id)
    result = repo.get_stat_block(document_id, name)
    if result is None:
        raise not_found(f"Unknown stat block: {name}")
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
        return ambiguous_stat_block(candidates)
    return chunk_to_stat_block_detail(result)
