from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from rpg_api.deps import get_raw_repo, require_document
from rpg_api.errors import not_found, pdf_not_found
from rpg_api.schemas import (
    ExtractorPageOut,
    PageBlockOut,
    PageExtractorsCompareOut,
    PageMetaOut,
    PageNodeOut,
)
from rpg_ingest.feedback.extractor_compare import compare_page_extractors
from rpg_ingest.feedback.visual_review import VisualReviewError, resolve_pdf_path
from rpg_ingest.raw.raw_nodes import NodeDepth, NodeType, flatten_raw_layout
from rpg_ingest.raw.rendering import render_pdf_pages
from rpg_core.storage.repositories.raw import RawRepository

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


@router.get("/{document_id}/pages/{page_number}/raw-layout")
def get_page_raw_layout(
    document_id: str,
    page_number: int,
    repo: RawRepository = Depends(get_raw_repo),
) -> dict[str, Any]:
    require_document(repo, document_id)
    raw_layout = repo.get_page_raw_layout(document_id, page_number)
    if raw_layout is None:
        raise not_found(f"Unknown page {page_number} for document {document_id}")
    return raw_layout


@router.get("/{document_id}/pages/{page_number}/nodes", response_model=list[PageNodeOut])
def list_page_nodes(
    document_id: str,
    page_number: int,
    level: NodeDepth | None = Query(default=None),
    node_type: NodeType | None = Query(default=None, alias="type"),
    repo: RawRepository = Depends(get_raw_repo),
) -> list[PageNodeOut]:
    require_document(repo, document_id)
    raw_layout = repo.get_page_raw_layout(document_id, page_number)
    if raw_layout is not None:
        nodes = flatten_raw_layout(raw_layout, level=level, node_type=node_type)
        return [
            PageNodeOut(
                id=node.id,
                depth=node.depth,
                node_type=node.node_type,
                parent_id=node.parent_id,
                block_index=node.block_index,
                line_index=node.line_index,
                span_index=node.span_index,
                text=node.text,
                bbox=node.bbox,
                metadata=node.metadata,
            )
            for node in nodes
        ]

    blocks = repo.list_page_blocks_for_page(document_id, page_number)
    if not blocks:
        raise not_found(
            f"Raw layout unavailable for page {page_number}. "
            "Re-import with --ingest-mode layout-only."
        )
    if level is not None and level != "block":
        return []
    if node_type is not None and node_type != "text":
        return []
    return [
        PageNodeOut(
            id=block.id,
            depth="block",
            node_type="text",
            parent_id=None,
            block_index=block.block_index,
            line_index=None,
            span_index=None,
            text=block.text,
            bbox=block.bbox,
            metadata=block.metadata,
        )
        for block in blocks
    ]


@router.get(
    "/{document_id}/pages/{page_number}/extractors-compare",
    response_model=PageExtractorsCompareOut,
)
def compare_page_extractors_endpoint(
    document_id: str,
    page_number: int,
    pdf_path: str | None = None,
    repo: RawRepository = Depends(get_raw_repo),
) -> PageExtractorsCompareOut:
    require_document(repo, document_id)
    try:
        resolved_pdf = resolve_pdf_path(repo, document_id, pdf_path)
    except VisualReviewError as exc:
        raise pdf_not_found(str(exc)) from exc

    try:
        payload = compare_page_extractors(
            resolved_pdf,
            page_number,
            repo=repo,
            document_id=document_id,
        )
    except ValueError as exc:
        raise not_found(str(exc)) from exc
    except FileNotFoundError as exc:
        raise pdf_not_found(str(exc)) from exc
    except RuntimeError as exc:
        raise not_found(str(exc)) from exc

    def _to_extractor_page(side: dict[str, Any]) -> ExtractorPageOut:
        return ExtractorPageOut(
            page_number=side["page_number"],
            width=side["width"],
            height=side["height"],
            extraction_method=side["extraction_method"],
            blocks=[PageBlockOut(**block) for block in side["blocks"]],
        )

    return PageExtractorsCompareOut(
        page_number=payload["page_number"],
        width=payload["width"],
        height=payload["height"],
        pymupdf=_to_extractor_page(payload["pymupdf"]),
        pdfbox=_to_extractor_page(payload["pdfbox"]),
    )


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
