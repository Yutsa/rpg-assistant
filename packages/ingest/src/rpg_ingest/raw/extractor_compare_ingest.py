from __future__ import annotations

from pathlib import Path
from typing import Any

import pymupdf

from rpg_core.models.raw import BBox, PageBlockRecord, PageRecord
from rpg_core.storage.ids import compare_block_id
from rpg_core.storage.repositories.raw import RawRepository
from rpg_ingest.raw.clojure_pdfbox import extract_pdfbox_document
from rpg_ingest.raw.layout import blocks_from_raw_layout
from rpg_ingest.raw.coverage import page_text_coverage_ratio

COMPARE_LANE_PYMUPDF = "pymupdf"
COMPARE_LANE_PDFBOX = "pdfbox"


def _bbox_from_dict(data: dict[str, Any]) -> BBox:
    return BBox(
        x0=float(data["x0"]),
        y0=float(data["y0"]),
        x1=float(data["x1"]),
        y1=float(data["y1"]),
    )


def extract_pymupdf_compare_page(document: pymupdf.Document, page_number: int) -> dict[str, Any]:
    if page_number < 1 or page_number > document.page_count:
        raise ValueError(
            f"Page {page_number} out of range (document has {document.page_count} pages)"
        )
    page = document[page_number - 1]
    rect = page.rect
    raw_layout = page.get_text("dict")
    blocks = blocks_from_raw_layout(raw_layout, page_number)
    return {
        "page_number": page_number,
        "width": float(rect.width),
        "height": float(rect.height),
        "extraction_method": "pymupdf_raw",
        "blocks": [
            {
                "block_index": block.block_index,
                "text": block.text,
                "bbox": block.bbox.model_dump(),
                "metadata": {
                    **block.metadata,
                    "source": "pymupdf_raw",
                    "compare_lane": COMPARE_LANE_PYMUPDF,
                },
            }
            for block in blocks
        ],
    }


def extract_compare_document_pages(pdf_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pdfbox_document = extract_pdfbox_document(pdf_path)
    pdfbox_pages = pdfbox_document["pages"]

    pymupdf_pages: list[dict[str, Any]] = []
    with pymupdf.open(pdf_path) as document:
        for page_number in range(1, document.page_count + 1):
            pymupdf_pages.append(extract_pymupdf_compare_page(document, page_number))

    if len(pymupdf_pages) != len(pdfbox_pages):
        raise RuntimeError(
            f"Page count mismatch: pymupdf={len(pymupdf_pages)} pdfbox={len(pdfbox_pages)}"
        )
    return pymupdf_pages, pdfbox_pages


def build_extractor_compare_records(
    *,
    document_id: str,
    pymupdf_pages: list[dict[str, Any]],
    pdfbox_pages: list[dict[str, Any]],
) -> tuple[list[PageRecord], list[PageBlockRecord]]:
    pages: list[PageRecord] = []
    blocks: list[PageBlockRecord] = []

    for pdfbox_page, pymupdf_page in zip(pdfbox_pages, pymupdf_pages, strict=True):
        page_number = int(pdfbox_page["page_number"])
        page_id = f"page_{document_id}_{page_number:04d}"
        pdfbox_text = "\n\n".join(
            str(block.get("text") or "") for block in pdfbox_page.get("blocks") or []
        ).strip()
        width = float(pdfbox_page["width"])
        height = float(pdfbox_page["height"])
        ratio = page_text_coverage_ratio(pdfbox_text, width, height)

        pages.append(
            PageRecord(
                id=page_id,
                document_id=document_id,
                page_number=page_number,
                text=pdfbox_text,
                extraction_method="extractor_compare",
                has_text=bool(pdfbox_text),
                text_coverage_ratio=ratio,
                width=width,
                height=height,
            )
        )

        for lane, page_payload in (
            (COMPARE_LANE_PDFBOX, pdfbox_page),
            (COMPARE_LANE_PYMUPDF, pymupdf_page),
        ):
            for block in page_payload.get("blocks") or []:
                block_index = int(block["block_index"])
                metadata = dict(block.get("metadata") or {})
                metadata.setdefault("compare_lane", lane)
                blocks.append(
                    PageBlockRecord(
                        id=compare_block_id(document_id, page_number, lane, block_index),
                        document_id=document_id,
                        page_id=page_id,
                        page_number=page_number,
                        block_index=block_index,
                        text=str(block.get("text") or ""),
                        bbox=_bbox_from_dict(block["bbox"]),
                        metadata=metadata,
                    )
                )

    return pages, blocks


def attach_compare_lanes(
    repo: RawRepository,
    *,
    document_id: str,
    pdf_path: Path,
) -> dict[str, int]:
    """Persist raw PyMuPDF + PDFBox blocks for the comparateur alongside a full import."""
    pymupdf_pages, pdfbox_pages = extract_compare_document_pages(pdf_path)
    _, compare_blocks = build_extractor_compare_records(
        document_id=document_id,
        pymupdf_pages=pymupdf_pages,
        pdfbox_pages=pdfbox_pages,
    )
    removed = repo.delete_compare_lane_blocks(document_id)
    repo.insert_page_blocks(compare_blocks)
    pymupdf_count = sum(
        1
        for block in compare_blocks
        if (block.metadata or {}).get("compare_lane") == COMPARE_LANE_PYMUPDF
    )
    pdfbox_count = sum(
        1
        for block in compare_blocks
        if (block.metadata or {}).get("compare_lane") == COMPARE_LANE_PDFBOX
    )
    return {
        "compare_lanes_removed": removed,
        "compare_lane_pymupdf_block_count": pymupdf_count,
        "compare_lane_pdfbox_block_count": pdfbox_count,
    }
