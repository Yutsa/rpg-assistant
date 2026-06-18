from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from rpg_api.deps import get_raw_repo, require_document
from rpg_api.errors import ambiguous_stat_block, not_found
from rpg_api.schemas import StatBlockIndexOut
from rpg_core.stat_blocks.serialize import (
    chunk_to_stat_block_detail,
    stat_block_ambiguity_candidates,
)
from rpg_core.storage.repositories.raw import RawRepository

router = APIRouter(prefix="/documents", tags=["stat-blocks"])


@router.get("/{document_id}/stat-blocks", response_model=list[StatBlockIndexOut])
def list_stat_blocks(
    document_id: str,
    repo: RawRepository = Depends(get_raw_repo),
) -> list[StatBlockIndexOut]:
    require_document(repo, document_id)
    return [
        StatBlockIndexOut(**entry.model_dump())
        for entry in repo.list_stat_blocks(document_id)
    ]


@router.get("/{document_id}/stat-blocks/{identifier}", response_model=None)
def get_stat_block(
    document_id: str,
    identifier: str,
    repo: RawRepository = Depends(get_raw_repo),
) -> dict[str, Any] | JSONResponse:
    require_document(repo, document_id)
    if identifier.startswith("chunk_"):
        result = repo.get_stat_block_by_chunk_id(document_id, identifier)
        if result is None:
            raise not_found(f"Unknown stat block chunk: {identifier}")
        return chunk_to_stat_block_detail(result)
    result = repo.get_stat_block(document_id, identifier)
    if result is None:
        raise not_found(f"Unknown stat block: {identifier}")
    if isinstance(result, list):
        return ambiguous_stat_block(stat_block_ambiguity_candidates(result))
    return chunk_to_stat_block_detail(result)
