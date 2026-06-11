from __future__ import annotations

import re
import unicodedata

from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage

SPATIAL_Y_TOLERANCE = 5.0
MIN_COLUMN_OVERLAP = 0.35
NARROW_BOX_MAX_WIDTH = 160.0
NARROW_BOX_X_MARGIN = 35.0
NARROW_BOX_MAX_VERTICAL_GAP = 130.0
DECORATIVE_FONT_RATIO = 2.0
DECORATIVE_MIN_FONT = 28.0
DECORATIVE_TOP_RATIO = 0.33
VERTICAL_HEADER_MAX_WIDTH = 20.0
VERTICAL_HEADER_MIN_X_RATIO = 0.85
TITLE_CASE_MAX_WORDS = 6
TITLE_CASE_MIN_WORDS = 2

ALL_CAPS_RE = re.compile(r"^[A-Z0-9ÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][A-Z0-9ÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ\s\-:,'\.]{2,}$")
TITLE_CASE_WORD_RE = re.compile(
    r"^[A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][\w''\-]+(?:\s+[a-zàâäéèêëïîôùûüÿç][\w''\-]+){1,5}$",
    re.UNICODE,
)
PAGE_FOOTER_RE = re.compile(r"PAGE\s+\d+\s*$", re.IGNORECASE)
CHAPTER_RE = re.compile(
    r"^(?:chapter|chapitre|part|partie)\s+(\d+|[IVXLC]+)\b",
    re.IGNORECASE,
)

META_BOX_HEADINGS = frozenset(
    {
        "EN QUELQUES MOTS",
        "FICHE TECHNIQUE",
    }
)


def _strip_glyphs(text: str) -> str:
    return "".join(
        ch for ch in text if unicodedata.category(ch) not in {"Cf", "Co", "Cs"}
    ).strip()


def spatial_sort_key(block: LayoutBlock) -> tuple[int, float, float]:
    y_bucket = round(block.bbox.y0 / SPATIAL_Y_TOLERANCE) * SPATIAL_Y_TOLERANCE
    return (block.page_number, y_bucket, block.bbox.x0)


def horizontal_overlap_ratio(left: LayoutBlock, right: LayoutBlock) -> float:
    overlap = min(left.bbox.x1, right.bbox.x1) - max(left.bbox.x0, right.bbox.x0)
    if overlap <= 0:
        return 0.0
    narrower = min(left.bbox.x1 - left.bbox.x0, right.bbox.x1 - right.bbox.x0)
    if narrower <= 0:
        return 0.0
    return overlap / narrower


def is_in_column_band(
    block: LayoutBlock,
    heading: LayoutBlock,
    *,
    min_overlap: float = MIN_COLUMN_OVERLAP,
) -> bool:
    return horizontal_overlap_ratio(block, heading) >= min_overlap


def is_narrow_heading_box(heading: LayoutBlock) -> bool:
    return (heading.bbox.x1 - heading.bbox.x0) <= NARROW_BOX_MAX_WIDTH


def is_in_heading_content_zone(
    block: LayoutBlock,
    heading: LayoutBlock,
    *,
    heading_text: str | None = None,
    min_overlap: float = MIN_COLUMN_OVERLAP,
) -> bool:
    if block.bbox.y0 <= heading.bbox.y1:
        return False
    if horizontal_overlap_ratio(block, heading) < min_overlap:
        return False
    if heading_text and is_meta_box_heading(heading_text):
        if block.bbox.x0 < heading.bbox.x0 - NARROW_BOX_X_MARGIN:
            return False
        if block.bbox.x1 > heading.bbox.x1 + NARROW_BOX_X_MARGIN:
            return False
        gap = block.bbox.y0 - heading.bbox.y1
        return 0 <= gap <= NARROW_BOX_MAX_VERTICAL_GAP
    return True


def page_median_font(blocks: list[LayoutBlock]) -> float:
    sizes = [
        b.metadata.get("max_font_size")
        for b in blocks
        if b.metadata.get("max_font_size")
    ]
    if not sizes:
        return 12.0
    sizes.sort()
    mid = len(sizes) // 2
    return sizes[mid] if len(sizes) % 2 else (sizes[mid - 1] + sizes[mid]) / 2


def is_decorative_spread_title(
    block: LayoutBlock,
    page: LayoutPage,
    *,
    median_font: float,
) -> bool:
    text = _strip_glyphs(block.text).strip()
    if not text or not ALL_CAPS_RE.match(text):
        return False
    max_font = block.metadata.get("max_font_size") or 0
    if (
        max_font < DECORATIVE_MIN_FONT
        and max_font < median_font * DECORATIVE_FONT_RATIO
    ):
        return False
    if block.bbox.y0 > page.height * DECORATIVE_TOP_RATIO:
        return False
    return len(text.split()) <= 4 and text.count("\n") <= 1


def is_spread_title_pair(
    upper: LayoutBlock,
    lower: LayoutBlock,
    page: LayoutPage,
    *,
    median_font: float,
) -> bool:
    if not is_decorative_spread_title(upper, page, median_font=median_font):
        return False
    lower_text = _strip_glyphs(lower.text).strip()
    if not lower_text or not ALL_CAPS_RE.match(lower_text):
        return False
    if lower.bbox.y0 > page.height * DECORATIVE_TOP_RATIO:
        return False
    if lower.bbox.y0 < upper.bbox.y1 - 5:
        return False
    return len(lower_text.split()) <= 4


def is_vertical_running_header(block: LayoutBlock, page: LayoutPage) -> bool:
    width = block.bbox.x1 - block.bbox.x0
    if width > VERTICAL_HEADER_MAX_WIDTH:
        return False
    if block.bbox.x0 < page.width * VERTICAL_HEADER_MIN_X_RATIO:
        return False
    text = _strip_glyphs(block.text).strip()
    return bool(text) and len(text) <= 80 and len(text.split()) <= 12


def is_page_footer_block(block: LayoutBlock, page: LayoutPage, *, footer_ratio: float = 0.08) -> bool:
    footer_limit = page.height * (1.0 - footer_ratio)
    if block.bbox.y0 <= footer_limit:
        return False
    return bool(PAGE_FOOTER_RE.search(_strip_glyphs(block.text)))


def is_title_case_heading(
    text: str,
    block: LayoutBlock,
    *,
    median_font: float,
) -> bool:
    cleaned = _strip_glyphs(text).strip()
    if not cleaned or not block.metadata.get("is_bold"):
        return False
    max_font = block.metadata.get("max_font_size") or 0
    if max_font < median_font * 1.05:
        return False
    words = cleaned.split()
    if not (TITLE_CASE_MIN_WORDS <= len(words) <= TITLE_CASE_MAX_WORDS):
        return False
    return bool(TITLE_CASE_WORD_RE.match(cleaned))


def is_meta_box_heading(text: str) -> bool:
    normalized = _strip_glyphs(text).strip().upper()
    return normalized in META_BOX_HEADINGS


def is_chapter_heading(text: str) -> bool:
    return bool(CHAPTER_RE.match(_strip_glyphs(text).strip()))


def find_block(
    pages: list[LayoutPage], page_number: int, block_index: int
) -> LayoutBlock | None:
    for page in pages:
        if page.page_number != page_number:
            continue
        for block in page.blocks:
            if block.block_index == block_index:
                return block
    return None


def spatially_sorted_headings(
    headings: list[tuple[int, int, str, int]],
    pages: list[LayoutPage],
) -> list[tuple[int, int, str, int]]:
    def sort_key(item: tuple[int, int, str, int]) -> tuple[int, float, float]:
        page_num, block_idx, _, _ = item
        block = find_block(pages, page_num, block_idx)
        if block is None:
            return (page_num, float(block_idx), 0.0)
        return spatial_sort_key(block)

    return sorted(headings, key=sort_key)


def page_is_sparse(page: LayoutPage, *, max_blocks: int = 2) -> bool:
    body_blocks = [
        b
        for b in page.blocks
        if not is_page_footer_block(b, page)
        and not is_vertical_running_header(b, page)
    ]
    return len(body_blocks) <= max_blocks
