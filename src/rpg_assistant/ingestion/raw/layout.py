from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pymupdf

from rpg_assistant.models.raw import BBox


@dataclass
class LayoutBlock:
    page_number: int
    block_index: int
    text: str
    bbox: BBox
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LayoutPage:
    page_number: int
    width: float
    height: float
    text: str
    blocks: list[LayoutBlock] = field(default_factory=list)


def rebuild_layout_page(page: LayoutPage, blocks: list[LayoutBlock]) -> LayoutPage:
    for index, block in enumerate(blocks):
        block.block_index = index
        block.page_number = page.page_number
    return LayoutPage(
        page_number=page.page_number,
        width=page.width,
        height=page.height,
        text="\n\n".join(block.text for block in blocks),
        blocks=blocks,
    )


def merge_block_bboxes(blocks: list[LayoutBlock]) -> BBox | None:
    if not blocks:
        return None
    return BBox(
        x0=min(block.bbox.x0 for block in blocks),
        y0=min(block.bbox.y0 for block in blocks),
        x1=max(block.bbox.x1 for block in blocks),
        y1=max(block.bbox.y1 for block in blocks),
    )


def _bbox_from_tuple(coords: tuple[float, ...]) -> BBox:
    return BBox(x0=coords[0], y0=coords[1], x1=coords[2], y1=coords[3])


def _line_metadata(line: dict[str, Any]) -> dict[str, Any]:
    spans = line.get("spans") or []
    if not spans:
        return {}
    primary = max(spans, key=lambda s: len(s.get("text", "")))
    return {
        "font_size": primary.get("size"),
        "font_flags": primary.get("flags"),
        "font_name": primary.get("font"),
    }


def extract_layout_pages(document: pymupdf.Document) -> list[LayoutPage]:
    """Extract structured text blocks with bounding boxes from a PDF."""
    pages: list[LayoutPage] = []
    for page_index, page in enumerate(document):
        page_number = page_index + 1
        rect = page.rect
        page_dict = page.get_text("dict")
        blocks: list[LayoutBlock] = []
        block_index = 0
        text_parts: list[str] = []

        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            lines = block.get("lines") or []
            line_texts: list[str] = []
            line_meta: list[dict[str, Any]] = []
            for line in lines:
                spans = line.get("spans") or []
                line_text = "".join(span.get("text", "") for span in spans).strip()
                if not line_text:
                    continue
                line_texts.append(line_text)
                line_meta.append(_line_metadata(line))

            block_text = "\n".join(line_texts).strip()
            if not block_text:
                continue

            text_parts.append(block_text)
            bbox = _bbox_from_tuple(tuple(block["bbox"]))
            metadata: dict[str, Any] = {"line_count": len(line_texts)}
            if line_meta:
                sizes = [m["font_size"] for m in line_meta if m.get("font_size")]
                flags = [m.get("font_flags", 0) for m in line_meta]
                if sizes:
                    metadata["max_font_size"] = max(sizes)
                    metadata["avg_font_size"] = sum(sizes) / len(sizes)
                metadata["is_bold"] = any(f & 16 for f in flags)
                metadata["is_italic"] = any(f & 2 for f in flags)

            blocks.append(
                LayoutBlock(
                    page_number=page_number,
                    block_index=block_index,
                    text=block_text,
                    bbox=bbox,
                    metadata=metadata,
                )
            )
            block_index += 1

        pages.append(
            LayoutPage(
                page_number=page_number,
                width=rect.width,
                height=rect.height,
                text="\n\n".join(text_parts),
                blocks=blocks,
            )
        )
    return pages
