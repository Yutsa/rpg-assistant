from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

import pymupdf
import pymupdf4llm

from rpg_ingest.raw.layout import LayoutBlock, LayoutPage, extract_layout_pages, rebuild_layout_page
from rpg_ingest.raw.reading_order import column_major_sort_key, page_median_font
from rpg_core.models.raw import BBox

ElementKind = Literal[
    "heading",
    "paragraph",
    "list",
    "table",
    "stat_block_candidate",
]

_SKIP_BOXCLASSES = frozenset(
    {
        "page-header",
        "page-footer",
        "picture",
        "caption",
        "footnote",
        "formula",
    }
)

_HEADING_BOXCLASSES = frozenset({"section-header", "title"})
_LIST_BOXCLASSES = frozenset({"list-item"})
_STAT_HEADER_RE = re.compile(r"\|\s*NC\s+\d+", re.IGNORECASE)


@dataclass
class ExtractedElement:
    kind: ElementKind
    text: str
    page: int
    bbox: BBox
    order: int
    block_index: int
    level: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Pymupdf4LlmExtraction:
    elements: list[ExtractedElement]
    layout_pages: list[LayoutPage]
    page_count: int


def _bbox_from_box(box: dict[str, Any]) -> BBox:
    return BBox(
        x0=float(box["x0"]),
        y0=float(box["y0"]),
        x1=float(box["x1"]),
        y1=float(box["y1"]),
    )


def _box_text(box: dict[str, Any]) -> str:
    table = box.get("table")
    if isinstance(table, dict):
        markdown = table.get("markdown")
        if isinstance(markdown, str) and markdown.strip():
            return markdown.strip()
        extract = table.get("extract")
        if isinstance(extract, list):
            rows = [
                " | ".join(str(cell) for cell in row)
                for row in extract
                if isinstance(row, list)
            ]
            if rows:
                return "\n".join(rows).strip()
    parts: list[str] = []
    for line in box.get("textlines") or []:
        for span in line.get("spans") or []:
            parts.append(span.get("text", ""))
    return "".join(parts).strip()


def _span_metadata(box: dict[str, Any]) -> dict[str, Any]:
    sizes: list[float] = []
    flags: list[int] = []
    for line in box.get("textlines") or []:
        for span in line.get("spans") or []:
            size = span.get("size")
            if size is not None:
                sizes.append(float(size))
            flags.append(int(span.get("flags", 0)))
    metadata: dict[str, Any] = {
        "boxclass": box.get("boxclass"),
        "line_count": len(box.get("textlines") or []),
    }
    if sizes:
        metadata["max_font_size"] = max(sizes)
        metadata["avg_font_size"] = sum(sizes) / len(sizes)
    metadata["is_bold"] = any(flag & 16 for flag in flags)
    metadata["is_italic"] = any(flag & 2 for flag in flags)
    return metadata


def _markdown_heading_level(markdown_text: str, start_pos: int) -> int:
    line_start = markdown_text.rfind("\n", 0, start_pos) + 1
    line_end = markdown_text.find("\n", start_pos)
    if line_end == -1:
        line_end = len(markdown_text)
    line = markdown_text[line_start:line_end]
    stripped = line.strip()
    if not stripped.startswith("#"):
        return 1
    hashes = 0
    for char in stripped:
        if char == "#":
            hashes += 1
        else:
            break
    if hashes and (len(stripped) == hashes or stripped[hashes] == " "):
        return min(hashes, 6)
    return 1


def _classify_box(
    boxclass: str,
    text: str,
    *,
    markdown_text: str,
    markdown_pos: tuple[int, int] | None,
) -> tuple[ElementKind, int | None]:
    if boxclass in _HEADING_BOXCLASSES:
        level = (
            _markdown_heading_level(markdown_text, markdown_pos[0])
            if markdown_pos is not None
            else 1
        )
        return "heading", level
    if boxclass == "table":
        return "table", None
    if boxclass in _LIST_BOXCLASSES:
        return "list", None
    if _STAT_HEADER_RE.search(text):
        return "stat_block_candidate", None
    return "paragraph", None


def _page_boxes_by_index(page_chunk: dict[str, Any]) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for page_box in page_chunk.get("page_boxes") or []:
        index = page_box.get("index")
        if isinstance(index, int):
            indexed[index] = page_box
    return indexed


def _normalized_text(text: str) -> str:
    return " ".join(text.split()).casefold()


def _text_already_covered(text: str, existing: list[str]) -> bool:
    needle = _normalized_text(text)
    if len(needle) < 3:
        return True
    for candidate in existing:
        haystack = _normalized_text(candidate)
        if needle in haystack or haystack in needle:
            return True
    return False


def _element_kind_for_block(block: LayoutBlock) -> tuple[ElementKind, int | None]:
    boxclass = block.metadata.get("pymupdf4llm_boxclass")
    if boxclass in _HEADING_BOXCLASSES:
        level = block.metadata.get("heading_level")
        return "heading", int(level) if level is not None else 1
    if boxclass == "table":
        return "table", None
    if boxclass in _LIST_BOXCLASSES:
        return "list", None
    if _STAT_HEADER_RE.search(block.text):
        return "stat_block_candidate", None
    return "paragraph", None


_COMPOUND_CHAPTER_RE = re.compile(
    r"^(?P<heading>PARTIE\s+[IVXLC\d]+\s*:.*?)(?P<body>(?:Corps|L['']|Il\s).*)$",
    re.IGNORECASE | re.DOTALL,
)


def _split_compound_blocks(pages: list[LayoutPage]) -> list[LayoutPage]:
    """Split blocks where a chapter heading and body were merged into one box."""
    result: list[LayoutPage] = []
    for page in pages:
        split_blocks: list[LayoutBlock] = []
        for block in page.blocks:
            match = _COMPOUND_CHAPTER_RE.match(block.text.strip())
            if not match:
                split_blocks.append(block)
                continue
            heading_text = match.group("heading").strip()
            body_text = match.group("body").strip()
            heading_height = max((block.bbox.y1 - block.bbox.y0) * 0.35, 12.0)
            split_blocks.append(
                LayoutBlock(
                    page_number=block.page_number,
                    block_index=0,
                    text=heading_text,
                    bbox=BBox(
                        x0=block.bbox.x0,
                        y0=block.bbox.y0,
                        x1=block.bbox.x1,
                        y1=block.bbox.y0 + heading_height,
                    ),
                    metadata={
                        **block.metadata,
                        "pymupdf4llm_boxclass": "section-header",
                        "heading_level": 1,
                        "split_from_compound": True,
                    },
                )
            )
            split_blocks.append(
                LayoutBlock(
                    page_number=block.page_number,
                    block_index=0,
                    text=body_text,
                    bbox=BBox(
                        x0=block.bbox.x0,
                        y0=block.bbox.y0 + heading_height,
                        x1=block.bbox.x1,
                        y1=block.bbox.y1,
                    ),
                    metadata={
                        **block.metadata,
                        "reconciled_from": block.metadata.get("reconciled_from"),
                    },
                )
            )
        if len(split_blocks) == len(page.blocks):
            result.append(page)
        else:
            result.append(rebuild_layout_page(page, split_blocks))
    return result


def _rebuild_elements_from_pages(pages: list[LayoutPage]) -> list[ExtractedElement]:
    elements: list[ExtractedElement] = []
    order = 0
    for page in pages:
        for block in page.blocks:
            kind, level = _element_kind_for_block(block)
            elements.append(
                ExtractedElement(
                    kind=kind,
                    text=block.text,
                    page=page.page_number,
                    bbox=block.bbox,
                    order=order,
                    block_index=block.block_index,
                    level=level,
                    metadata=dict(block.metadata),
                )
            )
            order += 1
    return elements


def reconcile_with_legacy_layout(
    document: pymupdf.Document,
    extraction: Pymupdf4LlmExtraction,
    *,
    min_legacy_ratio: float = 0.85,
) -> Pymupdf4LlmExtraction:
    """Fill gaps when PyMuPDF4LLM misses text blocks that legacy extraction finds."""
    legacy_pages = extract_layout_pages(document)
    legacy_by_page = {page.page_number: page for page in legacy_pages}
    reconciled_pages: list[LayoutPage] = []

    for llm_page in extraction.layout_pages:
        legacy_page = legacy_by_page.get(llm_page.page_number)
        if legacy_page is None:
            reconciled_pages.append(llm_page)
            continue

        llm_text_len = len(llm_page.text.strip())
        legacy_text_len = len(legacy_page.text.strip())
        existing_texts = [block.text for block in llm_page.blocks]
        supplemental: list[LayoutBlock] = []
        if legacy_text_len and llm_text_len / legacy_text_len < min_legacy_ratio:
            for legacy_block in legacy_page.blocks:
                if _text_already_covered(legacy_block.text, existing_texts):
                    continue
                supplemental.append(
                    LayoutBlock(
                        page_number=llm_page.page_number,
                        block_index=0,
                        text=legacy_block.text,
                        bbox=legacy_block.bbox,
                        metadata={
                            **legacy_block.metadata,
                            "reconciled_from": "legacy",
                        },
                    )
                )
                existing_texts.append(legacy_block.text)

        if not supplemental:
            reconciled_pages.append(llm_page)
            continue

        merged_blocks = list(llm_page.blocks) + supplemental
        merged_blocks.sort(key=lambda block: column_major_sort_key(llm_page, block))
        reconciled_pages.append(
            rebuild_layout_page(llm_page, merged_blocks)
        )

    reconciled_pages = _split_compound_blocks(reconciled_pages)
    elements = _rebuild_elements_from_pages(reconciled_pages)
    return Pymupdf4LlmExtraction(
        elements=elements,
        layout_pages=reconciled_pages,
        page_count=len(reconciled_pages),
    )


def extract_document_pymupdf4llm(document: pymupdf.Document) -> Pymupdf4LlmExtraction:
    """Extract ordered layout elements via PyMuPDF4LLM JSON + page markdown chunks."""
    json_payload = json.loads(pymupdf4llm.to_json(document))
    page_chunks = pymupdf4llm.to_markdown(document, page_chunks=True)
    chunk_by_page = {
        int(chunk["metadata"]["page_number"]): chunk for chunk in page_chunks
    }

    elements: list[ExtractedElement] = []
    layout_pages: list[LayoutPage] = []
    order = 0

    for page_data in json_payload.get("pages") or []:
        page_number = int(page_data["page_number"])
        width = float(page_data.get("width") or 0.0)
        height = float(page_data.get("height") or 0.0)
        page_chunk = chunk_by_page.get(page_number, {})
        markdown_text = str(page_chunk.get("text") or "")
        page_boxes = _page_boxes_by_index(page_chunk)

        blocks: list[LayoutBlock] = []
        block_index = 0
        text_parts: list[str] = []

        for box_index, box in enumerate(page_data.get("boxes") or []):
            boxclass = str(box.get("boxclass") or "text")
            if boxclass in _SKIP_BOXCLASSES:
                continue

            text = _box_text(box)
            if not text:
                continue

            page_box = page_boxes.get(box_index)
            markdown_pos = tuple(page_box["pos"]) if page_box and "pos" in page_box else None
            kind, level = _classify_box(
                boxclass,
                text,
                markdown_text=markdown_text,
                markdown_pos=markdown_pos,
            )
            metadata = _span_metadata(box)
            metadata["pymupdf4llm_box_index"] = box_index
            metadata["pymupdf4llm_boxclass"] = boxclass
            if level is not None:
                metadata["heading_level"] = level
            if markdown_pos is not None:
                metadata["markdown_pos"] = list(markdown_pos)

            bbox = _bbox_from_box(box)
            blocks.append(
                LayoutBlock(
                    page_number=page_number,
                    block_index=block_index,
                    text=text,
                    bbox=bbox,
                    metadata=metadata,
                )
            )
            elements.append(
                ExtractedElement(
                    kind=kind,
                    text=text,
                    page=page_number,
                    bbox=bbox,
                    order=order,
                    block_index=block_index,
                    level=level,
                    metadata=dict(metadata),
                )
            )
            text_parts.append(text)
            block_index += 1
            order += 1

        layout_pages.append(
            LayoutPage(
                page_number=page_number,
                width=width,
                height=height,
                text="\n\n".join(text_parts),
                blocks=blocks,
            )
        )

    extraction = Pymupdf4LlmExtraction(
        elements=elements,
        layout_pages=layout_pages,
        page_count=len(layout_pages),
    )
    return reconcile_with_legacy_layout(document, extraction)
