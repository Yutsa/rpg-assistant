from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from rpg_api.deps import get_raw_repo, require_document
from rpg_api.schemas import ChunkListItem, SectionOut
from rpg_core.storage.repositories.raw import RawRepository

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/sections", response_model=list[SectionOut])
def list_sections(
    document_id: str,
    repo: RawRepository = Depends(get_raw_repo),
) -> list[SectionOut]:
    require_document(repo, document_id)
    return [SectionOut(**s.model_dump()) for s in repo.list_sections(document_id)]


@router.get("/{document_id}/chunks", response_model=list[ChunkListItem])
def list_chunks(
    document_id: str,
    section_id: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repo: RawRepository = Depends(get_raw_repo),
) -> list[ChunkListItem]:
    require_document(repo, document_id)
    chunks = repo.list_chunks(
        document_id,
        section_id=section_id,
        page_start=page_start,
        page_end=page_end,
        limit=limit,
        offset=offset,
    )
    return [ChunkListItem.from_record(c) for c in chunks]
