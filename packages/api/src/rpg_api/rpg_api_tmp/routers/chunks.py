from __future__ import annotations

from fastapi import APIRouter, Depends

from rpg_assistant.api.deps import get_raw_repo
from rpg_assistant.api.errors import not_found
from rpg_assistant.api.schemas import ChunkOut
from rpg_assistant.storage.repositories.raw import RawRepository

router = APIRouter(prefix="/chunks", tags=["chunks"])


@router.get("/{chunk_id}", response_model=ChunkOut)
def get_chunk(
    chunk_id: str,
    repo: RawRepository = Depends(get_raw_repo),
) -> ChunkOut:
    chunk = repo.get_chunk(chunk_id)
    if chunk is None:
        raise not_found(f"Unknown chunk: {chunk_id}")
    return ChunkOut.from_record(chunk)
