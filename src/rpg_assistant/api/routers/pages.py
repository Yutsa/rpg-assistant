from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from rpg_assistant.api.deps import get_db
from rpg_assistant.api.errors import pdf_not_found
from rpg_assistant.api.schemas import PageBlockItem
from rpg_assistant.ingestion.feedback.visual_review import VisualReviewError, resolve_pdf_path
from rpg_assistant.ingestion.raw.rendering import render_pdf_pages
from rpg_assistant.storage.db import DatabaseConnection
from rpg_assistant.storage.repositories.raw import RawRepository

router = APIRouter(tags=["pages"])


@router.get("/documents/{document_id}/pages/{page_number}/render")
def render_document_page(
    document_id: str,
    page_number: int,
    dpi: int = Query(default=150, ge=72, le=300),
    pdf_path: str | None = None,
    conn: DatabaseConnection = Depends(get_db),
) -> FileResponse:
    repo = RawRepository(conn)
    try:
        resolved_pdf = resolve_pdf_path(repo, document_id, pdf_path_override=pdf_path)
        rendered = render_pdf_pages(
            resolved_pdf,
            [page_number],
            document_id=document_id,
            dpi=dpi,
        )
    except VisualReviewError as exc:
        raise pdf_not_found(str(exc)) from exc
    except ValueError as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    image_path = rendered[page_number]
    return FileResponse(
        path=image_path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/documents/{document_id}/pages/{page_number}/blocks",
    response_model=list[PageBlockItem],
)
def list_document_page_blocks(
    document_id: str,
    page_number: int,
    conn: DatabaseConnection = Depends(get_db),
) -> list[PageBlockItem]:
    blocks = RawRepository(conn).list_page_blocks(document_id, page_number)
    return [
        PageBlockItem(
            id=b.id,
            page_number=b.page_number,
            block_index=b.block_index,
            text=b.text,
            bbox=b.bbox,
            metadata=b.metadata,
        )
        for b in blocks
    ]
