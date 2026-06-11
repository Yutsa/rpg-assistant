from __future__ import annotations

import re

from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage
from rpg_assistant.models.raw import SectionRecord
from rpg_assistant.storage.ids import new_id

CHAPTER_RE = re.compile(
    r"^(?:chapter|chapitre|part|partie)\s+(\d+|[IVXLC]+)\b",
    re.IGNORECASE,
)
NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
ALL_CAPS_RE = re.compile(r"^[A-Z0-9][A-Z0-9\s\-:,'\.]{2,}$")


def _is_heading_candidate(block: LayoutBlock, page_median_font: float) -> bool:
    text = block.text.strip()
    if not text or len(text) > 120:
        return False
    if len(text.split()) > 14:
        return False

    meta = block.metadata
    max_font = meta.get("max_font_size") or 0
    is_bold = meta.get("is_bold", False)

    if CHAPTER_RE.match(text):
        return True
    if NUMBERED_HEADING_RE.match(text) and (is_bold or max_font >= page_median_font * 1.05):
        return True
    if ALL_CAPS_RE.match(text) and len(text) >= 4 and max_font >= page_median_font:
        return True
    if is_bold and max_font >= page_median_font * 1.15 and len(text) <= 80:
        return True
    return False


def _heading_level(text: str, max_font: float, page_median_font: float) -> int:
    if CHAPTER_RE.match(text):
        return 1
    numbered = NUMBERED_HEADING_RE.match(text)
    if numbered:
        depth = numbered.group(1).count(".") + 1
        return min(4, depth + 1)
    if max_font >= page_median_font * 1.3:
        return 1
    if max_font >= page_median_font * 1.15:
        return 2
    return 3


def _page_median_font(blocks: list[LayoutBlock]) -> float:
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


def detect_sections(
    pages: list[LayoutPage],
    *,
    campaign_id: str,
    document_id: str,
) -> list[SectionRecord]:
    headings: list[tuple[int, int, str, int]] = []
    for page in pages:
        median = _page_median_font(page.blocks)
        for block in page.blocks:
            if _is_heading_candidate(block, median):
                level = _heading_level(
                    block.text.strip(),
                    block.metadata.get("max_font_size") or median,
                    median,
                )
                headings.append(
                    (page.page_number, block.block_index, block.text.strip(), level)
                )

    if not headings:
        return [
            SectionRecord(
                id=new_id("sec"),
                campaign_id=campaign_id,
                document_id=document_id,
                title="Document",
                level=1,
                page_start=pages[0].page_number if pages else 1,
                page_end=pages[-1].page_number if pages else 1,
            )
        ]

    headings.sort(key=lambda h: (h[0], h[1]))
    page_count = pages[-1].page_number if pages else 1
    sections: list[SectionRecord] = []
    stack: list[tuple[int, str]] = []

    for index, (page_num, _block_idx, title, level) in enumerate(headings):
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent_id = stack[-1][1] if stack else None
        if index + 1 < len(headings):
            page_end = headings[index + 1][0]
        else:
            page_end = page_count
        section_id = new_id("sec")
        sections.append(
            SectionRecord(
                id=section_id,
                campaign_id=campaign_id,
                document_id=document_id,
                parent_section_id=parent_id,
                title=title,
                level=level,
                page_start=page_num,
                page_end=page_end,
            )
        )
        stack.append((level, section_id))

    return sections
