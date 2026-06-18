from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from rpg_ingest.raw.layout import (
    LayoutBlock,
    LayoutPage,
    merge_block_bboxes,
    rebuild_layout_page,
)
from rpg_ingest.raw.reading_order import (
    horizontal_overlap_ratio,
    is_editorial_credits_text,
    is_encadre_title_line,
)
from rpg_ingest.raw.stat_blocks.profile import StatBlockProfile

HYPHEN_CHARS = "-‐‑–—"
HYPHEN_END_RE = re.compile(rf"[{re.escape(HYPHEN_CHARS)}]\s*$")
STRONG_END_RE = re.compile(r"""[.!?»][\'")\]]*\s*$""")
NEW_UNIT_START_RE = re.compile(r"^[\s«•\-–—*]+|[A-Z][A-Z\s]{3,}")

DEFAULT_MAX_VERTICAL_GAP = 15.0
DEFAULT_MIN_COLUMN_OVERLAP = 0.25
MAX_VERTICAL_OVERLAP = 5.0
WRAP_TOP_ALIGN_TOLERANCE = 20.0
WRAP_MIN_EXTEND_PAST = 10.0
WRAP_VERTICAL_JUMP = 20.0
STYLE_FONT_SIZE_TOLERANCE = 1.5
COLUMN_CENTER_RATIO = 0.5

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


def _column_center(block: LayoutBlock) -> float:
    return (block.bbox.x0 + block.bbox.x1) / 2


def _is_left_column(block: LayoutBlock, *, page_width: float) -> bool:
    return _column_center(block) < page_width * COLUMN_CENTER_RATIO


def _is_right_column(block: LayoutBlock, *, page_width: float) -> bool:
    return _column_center(block) > page_width * COLUMN_CENTER_RATIO


def _compatible_style(
    previous: LayoutBlock,
    nxt: LayoutBlock,
    *,
    page_blocks: list[LayoutBlock] | None = None,
    next_idx: int | None = None,
    profile: StatBlockProfile | None = None,
) -> bool:
    if previous.metadata.get("is_italic") == nxt.metadata.get("is_italic"):
        return True
    if _looks_like_heading(
        nxt, page_blocks=page_blocks, block_idx=next_idx, profile=profile
    ):
        return False
    prev_size = previous.metadata.get("avg_font_size") or previous.metadata.get("max_font_size")
    next_size = nxt.metadata.get("avg_font_size") or nxt.metadata.get("max_font_size")
    if prev_size is None or next_size is None:
        return False
    return abs(prev_size - next_size) <= STYLE_FONT_SIZE_TOLERANCE


def _is_wrap_around_pair(
    previous: LayoutBlock,
    nxt: LayoutBlock,
    *,
    page_width: float,
    page_blocks: list[LayoutBlock] | None = None,
    next_idx: int | None = None,
    profile: StatBlockProfile | None = None,
) -> bool:
    if _same_column(previous, nxt):
        return False
    if not _is_left_column(previous, page_width=page_width):
        return False
    if not _is_right_column(nxt, page_width=page_width):
        return False
    if not _compatible_style(
        previous,
        nxt,
        page_blocks=page_blocks,
        next_idx=next_idx,
        profile=profile,
    ):
        return False
    if _ends_with_strong_punctuation(previous.text):
        return False
    if not _continues_sentence(nxt.text):
        return False
    if _starts_new_unit(nxt.text) or _looks_like_heading(
        nxt, page_blocks=page_blocks, block_idx=next_idx, profile=profile
    ):
        return False

    aligned_tops = abs(previous.bbox.y0 - nxt.bbox.y0) <= WRAP_TOP_ALIGN_TOLERANCE
    prev_extends_past_next = previous.bbox.y1 > nxt.bbox.y1 + WRAP_MIN_EXTEND_PAST
    beside_illustration = (
        aligned_tops and prev_extends_past_next and _shares_text_line(previous, nxt)
    )
    bottom_to_top = nxt.bbox.y0 < previous.bbox.y0 - WRAP_VERTICAL_JUMP
    return beside_illustration or bottom_to_top


def _looks_like_heading(
    block: LayoutBlock,
    *,
    page_blocks: list[LayoutBlock] | None = None,
    block_idx: int | None = None,
    profile: StatBlockProfile | None = None,
) -> bool:
    if block.metadata.get("stat_block_role") in {"header", "stats", "icon"}:
        return True
    if profile and page_blocks is not None and block_idx is not None:
        if profile.is_false_heading(block, page_blocks, block_idx):
            return True
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


def _merge_encadre_title_lines(
    previous: LayoutBlock,
    nxt: LayoutBlock,
) -> MergeKind | None:
    if not is_encadre_title_line(previous) or not is_encadre_title_line(nxt):
        return None
    if not _same_column(previous, nxt) or not _visually_adjacent(previous, nxt):
        return None
    return "line_break"


def _merge_kind(
    previous: LayoutBlock,
    nxt: LayoutBlock,
    *,
    page_width: float,
    page_blocks: list[LayoutBlock] | None = None,
    next_idx: int | None = None,
    profile: StatBlockProfile | None = None,
) -> MergeKind | None:
    if previous.page_number != nxt.page_number:
        return None
    encadre_merge = _merge_encadre_title_lines(previous, nxt)
    if encadre_merge is not None:
        return encadre_merge
    if _looks_like_heading(
        nxt, page_blocks=page_blocks, block_idx=next_idx, profile=profile
    ):
        return None
    if not _continues_sentence(nxt.text):
        return None
    if _ends_with_hyphen(previous.text):
        if _shares_text_line(previous, nxt) or _visually_adjacent(previous, nxt):
            return "hyphenation"
        return None
    if _is_wrap_around_pair(
        previous,
        nxt,
        page_width=page_width,
        page_blocks=page_blocks,
        next_idx=next_idx,
        profile=profile,
    ):
        return "line_break"
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


def _merge_page_blocks(
    blocks: list[LayoutBlock],
    *,
    page_width: float,
    profile: StatBlockProfile | None = None,
) -> tuple[list[LayoutBlock], int]:
    if len(blocks) < 2:
        return blocks, 0

    merged: list[LayoutBlock] = []
    merged_count = 0
    index = 0
    while index < len(blocks):
        current = blocks[index]
        next_index = index + 1
        while next_index < len(blocks):
            kind = _merge_kind(
                current,
                blocks[next_index],
                page_width=page_width,
                page_blocks=blocks,
                next_idx=next_index,
                profile=profile,
            )
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


def _cross_page_compatible_style(previous: LayoutBlock, nxt: LayoutBlock) -> bool:
    prev_size = previous.metadata.get("avg_font_size") or previous.metadata.get("max_font_size")
    next_size = nxt.metadata.get("avg_font_size") or nxt.metadata.get("max_font_size")
    if prev_size is None or next_size is None:
        return False
    return abs(prev_size - next_size) <= STYLE_FONT_SIZE_TOLERANCE


def _cross_page_merge_kind(
    previous: LayoutBlock,
    nxt: LayoutBlock,
    *,
    page_width: float,
) -> MergeKind | None:
    if previous.page_number + 1 != nxt.page_number:
        return None
    if _ends_with_strong_punctuation(previous.text):
        return None
    if not _continues_sentence(nxt.text):
        return None
    if not _cross_page_compatible_style(previous, nxt):
        return None
    same_column = horizontal_overlap_ratio(previous, nxt) >= DEFAULT_MIN_COLUMN_OVERLAP
    wrap_around = (
        previous.bbox.x0 >= page_width * 0.45
        and nxt.bbox.x0 < page_width * 0.45
    )
    if not same_column and not wrap_around:
        return None
    return "line_break"


def _merge_cross_page_blocks(pages: list[LayoutPage]) -> tuple[list[LayoutPage], int]:
    if len(pages) < 2:
        return pages, 0

    merged_count = 0
    page_blocks: list[list[LayoutBlock]] = [list(page.blocks) for page in pages]
    for index in range(len(pages) - 1):
        if not page_blocks[index] or not page_blocks[index + 1]:
            continue
        if any(is_editorial_credits_text(block.text) for block in page_blocks[index]):
            continue
        previous = page_blocks[index][-1]
        nxt = page_blocks[index + 1][0]
        kind = _cross_page_merge_kind(
            previous, nxt, page_width=pages[index].width
        )
        if kind is None:
            continue
        merged = _merge_two_blocks(previous, nxt, kind=kind)
        page_blocks[index].pop()
        page_blocks[index + 1][0] = LayoutBlock(
            page_number=nxt.page_number,
            block_index=nxt.block_index,
            text=merged.text,
            bbox=nxt.bbox,
            metadata=merged.metadata,
        )
        merged_count += 1

    return [
        rebuild_layout_page(page, blocks)
        for page, blocks in zip(pages, page_blocks, strict=True)
    ], merged_count


def merge_fragmented_blocks(
    pages: list[LayoutPage],
    *,
    profile: StatBlockProfile | None = None,
) -> BlockMergeResult:
    """Merge hyphenated and mid-sentence line-break fragments before chunking."""
    if not pages:
        return BlockMergeResult(pages=[], merged_block_count=0)

    merged_pages: list[LayoutPage] = []
    merged_block_count = 0
    for page in pages:
        blocks, page_merged = _merge_page_blocks(
            page.blocks, page_width=page.width, profile=profile
        )
        merged_block_count += page_merged
        merged_pages.append(rebuild_layout_page(page, blocks))

    cross_merged_pages, cross_merged_count = _merge_cross_page_blocks(merged_pages)

    return BlockMergeResult(
        pages=cross_merged_pages,
        merged_block_count=merged_block_count + cross_merged_count,
    )
