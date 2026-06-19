"""Enrich Docling structure with PyMuPDF block granularity."""

from __future__ import annotations

from rpg_ingest.raw.docling_convert import elements_to_layout_pages
from rpg_ingest.raw.elements import HEADING_ELEMENT_TYPES, DocElement
from rpg_ingest.raw.layout import LayoutBlock, LayoutPage
from rpg_ingest.raw.reading_order import (
    column_major_sort_key,
    is_list_item_block,
    is_meta_box_heading,
    page_median_font,
)
from rpg_ingest.raw.sections import _is_heading_candidate
from rpg_core.models.raw import BBox


def _bbox_area(bbox: BBox) -> float:
    return max(0.0, bbox.x1 - bbox.x0) * max(0.0, bbox.y1 - bbox.y0)


def _bbox_intersection(a: BBox, b: BBox) -> float:
    x0 = max(a.x0, b.x0)
    y0 = max(a.y0, b.y0)
    x1 = min(a.x1, b.x1)
    y1 = min(a.y1, b.y1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)


def _match_score(element: DocElement, block: LayoutBlock) -> float:
    intersection = _bbox_intersection(element.bbox, block.bbox)
    if intersection > 0:
        block_area = max(_bbox_area(block.bbox), 1.0)
        return intersection / block_area
    block_text = block.text.strip().casefold()
    element_text = element.text.strip().casefold()
    if not block_text or not element_text:
        return 0.0
    if block_text in element_text:
        return 0.45 + 0.45 * (len(block_text) / len(element_text))
    if element_text in block_text:
        return 0.35
    return 0.0


def _infer_element_type(block: LayoutBlock, page: LayoutPage) -> str:
    text = block.text.strip()
    if is_meta_box_heading(text):
        return "heading"
    if is_list_item_block(block):
        return "list_item"
    return "paragraph"


def _heading_level_from_block(
    block: LayoutBlock,
    page: LayoutPage,
    *,
    docling_level: int | None,
) -> int:
    median = page_median_font(page.blocks)
    max_font = block.metadata.get("max_font_size") or median
    base = docling_level or 1
    if max_font >= median * 1.35:
        return 1
    if max_font >= median * 1.12:
        return max(2, base)
    return max(3, base)


def _heading_candidate_score(block: LayoutBlock, page: LayoutPage) -> float:
    page_blocks = page.blocks
    block_idx = next(
        (idx for idx, candidate in enumerate(page_blocks) if candidate is block),
        0,
    )
    median = page_median_font(page_blocks)
    if _is_heading_candidate(
        block, page, median, page_blocks, block_idx, profile=None
    ):
        max_font = block.metadata.get("max_font_size") or median
        return max_font + (10.0 if block.metadata.get("is_bold") else 0.0)
    if is_meta_box_heading(block.text):
        return 100.0
    return 0.0


def enrich_docling_with_pymupdf(
    docling_elements: list[DocElement],
    pymupdf_pages: list[LayoutPage],
) -> tuple[list[DocElement], list[LayoutPage]]:
    """Replace Docling blocks with PyMuPDF blocks while preserving Docling labels."""
    pages_by_number = {page.page_number: page for page in pymupdf_pages}
    elements_by_page: dict[int, list[DocElement]] = {}
    for element in docling_elements:
        elements_by_page.setdefault(element.page_number, []).append(element)

    enriched: list[DocElement] = []
    element_index = 0

    for page_number in sorted(pages_by_number):
        page = pages_by_number[page_number]
        page_docling = sorted(
            elements_by_page.get(page_number, []),
            key=lambda element: element.element_index,
        )
        block_to_docling: dict[int, DocElement] = {}
        for block_idx, block in enumerate(page.blocks):
            best_score = 0.0
            best_element: DocElement | None = None
            for element in page_docling:
                score = _match_score(element, block)
                if score > best_score:
                    best_score = score
                    best_element = element
            if best_element is not None and best_score > 0.05:
                block_to_docling[block_idx] = best_element

        heading_anchor_for_element: dict[int, int] = {}
        for element in page_docling:
            if element.element_type not in HEADING_ELEMENT_TYPES:
                continue
            matched_indices = [
                block_idx
                for block_idx, matched in block_to_docling.items()
                if matched.element_index == element.element_index
            ]
            if not matched_indices:
                continue
            heading_anchor_for_element[element.element_index] = max(
                matched_indices,
                key=lambda block_idx: _heading_candidate_score(
                    page.blocks[block_idx], page
                ),
            )

        def reading_order_key(block_idx: int) -> tuple[int, float, float, float]:
            element = block_to_docling.get(block_idx)
            block = page.blocks[block_idx]
            spatial = column_major_sort_key(page, block)
            if element is None:
                return (10_000 + block_idx, *spatial[1:])
            return (element.element_index, *spatial[1:])

        for block_idx in sorted(range(len(page.blocks)), key=reading_order_key):
            block = page.blocks[block_idx]
            element = block_to_docling.get(block_idx)
            if (
                element is not None
                and element.element_type in HEADING_ELEMENT_TYPES
                and heading_anchor_for_element.get(element.element_index) == block_idx
            ):
                element_type = (
                    "title" if element.element_type == "title" else "heading"
                )
                heading_level = _heading_level_from_block(
                    block, page, docling_level=element.heading_level
                )
            else:
                element_type = _infer_element_type(block, page)
                heading_level = (
                    _heading_level_from_block(block, page, docling_level=1)
                    if element_type == "heading"
                    else None
                )

            metadata = dict(block.metadata)
            metadata["element_type"] = element_type
            if element is not None:
                metadata["docling_label"] = element.metadata.get("docling_label", "")

            enriched.append(
                DocElement(
                    element_index=element_index,
                    element_type=element_type,
                    text=block.text,
                    page_number=page_number,
                    block_index=block_idx,
                    bbox=block.bbox,
                    heading_level=heading_level,
                    metadata=metadata,
                )
            )
            element_index += 1

    page_sizes = {
        page.page_number: (page.width, page.height) for page in pymupdf_pages
    }
    layout_pages = elements_to_layout_pages(enriched, page_sizes=page_sizes)
    return enriched, layout_pages
