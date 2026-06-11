from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from rpg_assistant.api.deps import get_raw_repo
from rpg_assistant.api.errors import not_found
from rpg_assistant.api.schemas import ChunkListItem, SectionOut
from rpg_assistant.storage.repositories.raw import RawRepository

router = APIRouter(prefix="/documents", tags=["documents"])


def _require_document(repo: RawRepository, document_id: str) -> None:
    if repo.get_document(document_id) is None:
        raise not_found(f"Unknown document: {document_id}")


@router.get("/{document_id}/sections", response_model=list[SectionOut])
def list_sections(
    document_id: str,
    repo: RawRepository = Depends(get_raw_repo),
) -> list[SectionOut]:
    _require_document(repo, document_id)
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
    _require_document(repo, document_id)
    chunks = repo.list_chunks(
        document_id,
        section_id=section_id,
        page_start=page_start,
        page_end=page_end,
        limit=limit,
        offset=offset,
    )
    return [
        ChunkListItem(
            id=c.id,
            section_id=c.section_id,
            page_start=c.page_start,
            page_end=c.page_end,
            chunk_type=c.chunk_type,
            chunk_type_hint=c.chunk_type_hint,
            token_count=c.token_count,
            needs_rechunk=c.needs_rechunk,
            text_preview=c.text[:200],
        )
        for c in chunks
    ]
