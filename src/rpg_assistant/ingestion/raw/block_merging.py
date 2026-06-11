from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from rpg_assistant.ingestion.raw.layout import (
    LayoutBlock,
    LayoutPage,
    merge_block_bboxes,
    rebuild_layout_page,
)

HYPHEN_CHARS = "-‐‑–—"
HYPHEN_END_RE = re.compile(rf"[{re.escape(HYPHEN_CHARS)}]\s*$")
STRONG_END_RE = re.compile(r"""[.!?»][\'")\]]*\s*$""")
NEW_UNIT_START_RE = re.compile(r"^[\s«•\-–—*]+|[A-Z][A-Z\s]{3,}")

DEFAULT_MAX_VERTICAL_GAP = 15.0
DEFAULT_MIN_COLUMN_OVERLAP = 0.25
MAX_VERTICAL_OVERLAP = 5.0

MergeKind = Literal["hyphenation", "line_break"]


@dataclass
class BlockMergeResult:
    pages: list[LayoutPage]
    merged_block_count: int


def _ends_with_hyphen(text: str) -> bool:
    return bool(HYPHEN_END_RE.search(text.rstrip()))


def _ends_with_strong_punctuation(text: str) -> bool:
    return bool(STRONG_END_RE.search(text.rstrip()))


def _continues_sentence(text: str) -> bool:
    stripped = text.lstrip()
    return bool(stripped) and stripped[0].islower()


def _starts_new_unit(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return True
    return bool(NEW_UNIT_START_RE.match(stripped))


def _visually_adjacent(
    previous: LayoutBlock,
    nxt: LayoutBlock,
    *,
    max_gap: float = DEFAULT_MAX_VERTICAL_GAP,
) -> bool:
    gap = nxt.bbox.y0 - previous.bbox.y1
    return -MAX_VERTICAL_OVERLAP <= gap <= max_gap


def _shares_text_line(previous: LayoutBlock, nxt: LayoutBlock) -> bool:
    overlap = min(previous.bbox.y1, nxt.bbox.y1) - max(previous.bbox.y0, nxt.bbox.y0)
    return overlap > 0


def _same_column(
    previous: LayoutBlock,
    nxt: LayoutBlock,
    *,
    min_overlap_ratio: float = DEFAULT_MIN_COLUMN_OVERLAP,
) -> bool:
    overlap = min(previous.bbox.x1, nxt.bbox.x1) - max(previous.bbox.x0, nxt.bbox.x0)
    if overlap <= 0:
        return False
    narrower = min(previous.bbox.x1 - previous.bbox.x0, nxt.bbox.x1 - nxt.bbox.x0)
    if narrower <= 0:
        return False
    return overlap / narrower >= min_overlap_ratio


def _looks_like_heading(block: LayoutBlock) -> bool:
    text = block.text.strip()
    if not text:
        return False
    metadata = block.metadata
    font_size = metadata.get("avg_font_size") or metadata.get("max_font_size") or 0
    if metadata.get("is_bold") and len(text) < 80 and font_size >= 12:
        return True
    return len(text) < 50 and text.isupper()


def _is_drop_cap_pair(previous: LayoutBlock, nxt: LayoutBlock) -> bool:
    text = previous.text.strip()
    if len(text) != 1 or not text.isupper():
        return False
    if not _continues_sentence(nxt.text):
        return False
    if previous.page_number != nxt.page_number:
        return False
    font_size = previous.metadata.get("max_font_size") or 0
    if font_size < 12:
        return False
    return nxt.bbox.x0 >= previous.bbox.x0 - 5


def _merge_kind(previous: LayoutBlock, nxt: LayoutBlock) -> MergeKind | None:
    if previous.page_number != nxt.page_number:
        return None
    if _looks_like_heading(nxt):
        return None
    if not _continues_sentence(nxt.text):
        return None
    if _ends_with_hyphen(previous.text):
        if _shares_text_line(previous, nxt) or _visually_adjacent(previous, nxt):
            return "hyphenation"
        return None
    if not _visually_adjacent(previous, nxt):
        return None
    if not _same_column(previous, nxt):
        return None
    if _ends_with_strong_punctuation(previous.text):
        return None
    if _starts_new_unit(nxt.text):
        return None
    return "line_break"


def _merge_metadata(previous: LayoutBlock, nxt: LayoutBlock) -> dict:
    merged = dict(previous.metadata)
    next_meta = nxt.metadata
    merged["line_count"] = merged.get("line_count", 0) + next_meta.get("line_count", 0)
    for key in ("max_font_size", "avg_font_size"):
        values = [
            value
            for value in (merged.get(key), next_meta.get(key))
            if value is not None
        ]
        if not values:
            continue
        if key == "max_font_size":
            merged[key] = max(values)
        else:
            merged[key] = sum(values) / len(values)
    merged["is_bold"] = merged.get("is_bold") or next_meta.get("is_bold")
    merged["is_italic"] = merged.get("is_italic") or next_meta.get("is_italic")
    return merged


def _merge_text(previous: str, nxt: str, *, hyphenation: bool) -> str:
    if hyphenation:
        left = previous.rstrip()
        while left and left[-1] in HYPHEN_CHARS:
            left = left[:-1].rstrip()
        return left + nxt.lstrip()
    return previous.rstrip() + " " + nxt.lstrip()


def _merge_two_blocks(
    previous: LayoutBlock, nxt: LayoutBlock, *, kind: MergeKind
) -> LayoutBlock:
    bbox = merge_block_bboxes([previous, nxt])
    assert bbox is not None
    return LayoutBlock(
        page_number=previous.page_number,
        block_index=previous.block_index,
        text=_merge_text(previous.text, nxt.text, hyphenation=kind == "hyphenation"),
        bbox=bbox,
        metadata=_merge_metadata(previous, nxt),
    )


def _merge_page_blocks(blocks: list[LayoutBlock]) -> tuple[list[LayoutBlock], int]:
    if len(blocks) < 2:
        return blocks, 0

    merged: list[LayoutBlock] = []
    merged_count = 0
    index = 0
    while index < len(blocks):
        current = blocks[index]
        next_index = index + 1
        while next_index < len(blocks):
            kind = _merge_kind(current, blocks[next_index])
            if kind is None:
                break
            current = _merge_two_blocks(current, blocks[next_index], kind=kind)
            merged_count += 1
            next_index += 1
        merged.append(current)
        index = next_index
    return merged, merged_count


def _merge_drop_cap_pair(previous: LayoutBlock, nxt: LayoutBlock) -> LayoutBlock:
    bbox = merge_block_bboxes([previous, nxt])
    assert bbox is not None
    return LayoutBlock(
        page_number=previous.page_number,
        block_index=previous.block_index,
        text=previous.text.strip() + nxt.text.lstrip(),
        bbox=bbox,
        metadata=_merge_metadata(previous, nxt),
    )


def _merge_drop_caps_on_page(blocks: list[LayoutBlock]) -> tuple[list[LayoutBlock], int]:
    if len(blocks) < 2:
        return blocks, 0

    merged: list[LayoutBlock] = []
    merged_count = 0
    index = 0
    while index < len(blocks):
        current = blocks[index]
        if index + 1 < len(blocks) and _is_drop_cap_pair(current, blocks[index + 1]):
            current = _merge_drop_cap_pair(current, blocks[index + 1])
            merged_count += 1
            index += 2
        else:
            index += 1
        merged.append(current)
    return merged, merged_count


def merge_drop_caps(pages: list[LayoutPage]) -> BlockMergeResult:
    """Merge decorative drop-cap letters with the following body text block."""
    if not pages:
        return BlockMergeResult(pages=[], merged_block_count=0)

    merged_pages: list[LayoutPage] = []
    merged_block_count = 0
    for page in pages:
        blocks, page_merged = _merge_drop_caps_on_page(page.blocks)
        merged_block_count += page_merged
        merged_pages.append(rebuild_layout_page(page, blocks))

    return BlockMergeResult(
        pages=merged_pages,
        merged_block_count=merged_block_count,
    )


def merge_fragmented_blocks(pages: list[LayoutPage]) -> BlockMergeResult:
    """Merge hyphenated and mid-sentence line-break fragments before chunking."""
    if not pages:
        return BlockMergeResult(pages=[], merged_block_count=0)

    merged_pages: list[LayoutPage] = []
    merged_block_count = 0
    for page in pages:
        blocks, page_merged = _merge_page_blocks(page.blocks)
        merged_block_count += page_merged
        merged_pages.append(rebuild_layout_page(page, blocks))

    return BlockMergeResult(
        pages=merged_pages,
        merged_block_count=merged_block_count,
    )
