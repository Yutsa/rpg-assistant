from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from rpg_assistant.api.deps import get_raw_repo, require_document
from rpg_assistant.api.errors import not_found, pdf_not_found
from rpg_assistant.api.schemas import PageBlockOut, PageMetaOut
from rpg_assistant.ingestion.feedback.visual_review import VisualReviewError, resolve_pdf_path
from rpg_assistant.ingestion.raw.rendering import render_pdf_pages
from rpg_assistant.storage.repositories.raw import RawRepository

router = APIRouter(prefix="/documents", tags=["pages"])


@router.get("/{document_id}/pages/{page_number}", response_model=PageMetaOut)
def get_page_meta(
    document_id: str,
    page_number: int,
    repo: RawRepository = Depends(get_raw_repo),
) -> PageMetaOut:
    require_document(repo, document_id)
    page = repo.get_page(document_id, page_number)
    if page is None:
        raise not_found(f"Unknown page {page_number} for document {document_id}")
    if page.width is None or page.height is None:
        raise not_found(f"Page dimensions missing for page {page_number}")
    return PageMetaOut(
        page_number=page.page_number,
        width=page.width,
        height=page.height,
    )


@router.get("/{document_id}/pages/{page_number}/blocks", response_model=list[PageBlockOut])
def list_page_blocks(
    document_id: str,
    page_number: int,
    repo: RawRepository = Depends(get_raw_repo),
) -> list[PageBlockOut]:
    require_document(repo, document_id)
    blocks = repo.list_page_blocks_for_page(document_id, page_number)
    return [
        PageBlockOut(
            id=b.id,
            page_number=b.page_number,
            block_index=b.block_index,
            text=b.text,
            bbox=b.bbox,
            metadata=b.metadata,
        )
        for b in blocks
    ]


@router.get("/{document_id}/pages/{page_number}/render")
def render_page(
    document_id: str,
    page_number: int,
    dpi: int = Query(default=150, ge=72, le=300),
    pdf_path: str | None = None,
    repo: RawRepository = Depends(get_raw_repo),
) -> FileResponse:
    require_document(repo, document_id)
    try:
        resolved_pdf = resolve_pdf_path(repo, document_id, pdf_path)
    except VisualReviewError as exc:
        raise pdf_not_found(str(exc)) from exc

    try:
        rendered = render_pdf_pages(
            resolved_pdf,
            [page_number],
            document_id=document_id,
            dpi=dpi,
        )
    except ValueError as exc:
        raise not_found(str(exc)) from exc
    except FileNotFoundError as exc:
        raise pdf_not_found(str(exc)) from exc

    image_path = rendered.get(page_number)
    if image_path is None or not image_path.is_file():
        raise not_found(f"Failed to render page {page_number}")

    return FileResponse(
        image_path,
        media_type="image/png",
        filename=image_path.name,
    )
