from __future__ import annotations

import re
from dataclasses import dataclass, field

from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage
from rpg_assistant.ingestion.raw.reading_order import (
    find_block,
    is_chapter_heading,
    is_decorative_spread_title,
    is_meta_box_heading,
    is_spread_title_pair,
    is_title_case_heading,
    is_vertical_running_header,
    page_median_font,
    spatially_sorted_headings,
)
from rpg_assistant.ingestion.raw.stat_blocks.profile import StatBlockProfile
from rpg_assistant.models.raw import SectionRecord
from rpg_assistant.storage.ids import new_id

CHAPTER_RE = re.compile(
    r"^(?:chapter|chapitre|part|partie)\s+(\d+|[IVXLC]+)\b",
    re.IGNORECASE,
)
NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
ALL_CAPS_RE = re.compile(r"^[A-Z0-9][A-Z0-9\s\-:,'\.]{2,}$")

MIN_BOLD_HEADING_LEN = 3
PREAMBLE_TITLE = "Introduction"


@dataclass
class SectionDetectionResult:
    sections: list[SectionRecord]
    heading_anchors: list[tuple[int, int]]
    content_only_section_ids: frozenset[str] = field(default_factory=frozenset)


def _is_drop_cap_false_heading(
    block: LayoutBlock, page_blocks: list[LayoutBlock], block_idx: int
) -> bool:
    text = block.text.strip()
    if len(text) != 1 or not text.isupper():
        return False
    if block_idx + 1 >= len(page_blocks):
        return False
    nxt_text = page_blocks[block_idx + 1].text.lstrip()
    return bool(nxt_text) and nxt_text[0].islower()


def _is_heading_candidate(
    block: LayoutBlock,
    page: LayoutPage,
    page_median_font: float,
    page_blocks: list[LayoutBlock],
    block_idx: int,
    *,
    profile: StatBlockProfile | None = None,
) -> bool:
    text = block.text.strip()
    if not text or len(text) > 120:
        return False
    if len(text.split()) > 14:
        return False
    if block.metadata.get("stat_block_role") in {"header", "stats", "icon"}:
        return False
    if profile and profile.is_false_heading(block, page_blocks, block_idx):
        return False
    if _is_drop_cap_false_heading(block, page_blocks, block_idx):
        return False
    if is_vertical_running_header(block, page):
        return False
    if is_decorative_spread_title(block, page, median_font=page_median_font):
        return False
    if block_idx > 0 and is_spread_title_pair(
        page_blocks[block_idx - 1],
        block,
        page,
        median_font=page_median_font,
    ):
        return False

    meta = block.metadata
    max_font = meta.get("max_font_size") or 0
    is_bold = meta.get("is_bold", False)

    if CHAPTER_RE.match(text):
        return True
    if is_meta_box_heading(text):
        return True
    if is_title_case_heading(text, block, median_font=page_median_font):
        return True
    if NUMBERED_HEADING_RE.match(text) and (is_bold or max_font >= page_median_font * 1.05):
        return True
    if ALL_CAPS_RE.match(text) and len(text) >= 4 and max_font >= page_median_font:
        return True
    if (
        is_bold
        and max_font >= page_median_font * 1.15
        and MIN_BOLD_HEADING_LEN <= len(text) <= 80
    ):
        return True
    return False


def _heading_level(
    text: str,
    block: LayoutBlock,
    *,
    page_median_font: float,
) -> int:
    if is_meta_box_heading(text) or is_title_case_heading(
        text, block, median_font=page_median_font
    ):
        return 1
    if CHAPTER_RE.match(text):
        return 1
    numbered = NUMBERED_HEADING_RE.match(text)
    if numbered:
        depth = numbered.group(1).count(".") + 1
        return min(4, depth + 1)
    max_font = block.metadata.get("max_font_size") or page_median_font
    if max_font >= page_median_font * 1.3:
        return 1
    if max_font >= page_median_font * 1.15:
        return 2
    return 3


def _detect_preamble_sections(
    pages: list[LayoutPage],
    heading_positions: set[tuple[int, int]],
    *,
    campaign_id: str,
    document_id: str,
) -> tuple[list[SectionRecord], list[tuple[int, int]], frozenset[str]]:
    preamble_sections: list[SectionRecord] = []
    preamble_anchors: list[tuple[int, int]] = []
    content_only_ids: list[str] = []

    for page in pages:
        chapter_blocks = [
            (idx, block)
            for idx, block in enumerate(page.blocks)
            if is_chapter_heading(block.text)
        ]
        if not chapter_blocks:
            continue
        chapter_idx, chapter_block = min(chapter_blocks, key=lambda item: item[1].bbox.y0)
        meta_heading_blocks = [
            block
            for idx, block in enumerate(page.blocks)
            if (page.page_number, idx) in heading_positions and is_meta_box_heading(block.text)
        ]

        for block_idx, block in enumerate(page.blocks):
            if (page.page_number, block_idx) in heading_positions:
                continue
            if block.bbox.y0 >= chapter_block.bbox.y0:
                continue
            if block.metadata.get("stat_block_role") in {"header", "stats", "icon"}:
                continue
            if any(
                block.bbox.y0 >= meta.bbox.y0 and is_meta_box_heading(meta.text)
                for meta in meta_heading_blocks
                if block.bbox.y0 > meta.bbox.y1
            ):
                claimed_by_meta = any(
                    block.bbox.y0 <= meta.bbox.y1 + 130
                    and block.bbox.x0 >= meta.bbox.x0 - 35
                    and block.bbox.x1 <= meta.bbox.x1 + 35
                    for meta in meta_heading_blocks
                )
                if claimed_by_meta:
                    continue

            section_id = new_id("sec")
            preamble_sections.append(
                SectionRecord(
                    id=section_id,
                    campaign_id=campaign_id,
                    document_id=document_id,
                    parent_section_id=None,
                    title=PREAMBLE_TITLE,
                    level=1,
                    page_start=page.page_number,
                    page_end=page.page_number,
                )
            )
            preamble_anchors.append((page.page_number, block_idx))
            content_only_ids.append(section_id)
            break

    return preamble_sections, preamble_anchors, frozenset(content_only_ids)


def detect_sections(
    pages: list[LayoutPage],
    *,
    campaign_id: str,
    document_id: str,
    profile: StatBlockProfile | None = None,
) -> SectionDetectionResult:
    headings: list[tuple[int, int, str, int]] = []
    page_medians: dict[int, float] = {}

    for page in pages:
        median = page_median_font(page.blocks)
        page_medians[page.page_number] = median
        for block_idx, block in enumerate(page.blocks):
            if _is_heading_candidate(
                block, page, median, page.blocks, block_idx, profile=profile
            ):
                level = _heading_level(
                    block.text.strip(),
                    block,
                    page_median_font=median,
                )
                headings.append(
                    (page.page_number, block.block_index, block.text.strip(), level)
                )

    if not headings:
        fallback = SectionRecord(
            id=new_id("sec"),
            campaign_id=campaign_id,
            document_id=document_id,
            title="Document",
            level=1,
            page_start=pages[0].page_number if pages else 1,
            page_end=pages[-1].page_number if pages else 1,
        )
        return SectionDetectionResult(sections=[fallback], heading_anchors=[])

    headings = spatially_sorted_headings(headings, pages)
    page_count = pages[-1].page_number if pages else 1
    sections: list[SectionRecord] = []
    anchors: list[tuple[int, int]] = []
    stack: list[tuple[int, str]] = []

    for index, (page_num, block_idx, title, level) in enumerate(headings):
        block = find_block(pages, page_num, block_idx)
        median = page_medians.get(page_num, 12.0)

        if is_chapter_heading(title) or (
            block
            and (is_meta_box_heading(title) or is_title_case_heading(title, block, median_font=median))
        ):
            while stack:
                stack.pop()
            level = 1
            parent_id = None
        else:
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
        anchors.append((page_num, block_idx))
        stack.append((level, section_id))

    heading_positions = {(page_num, block_idx) for page_num, block_idx, _, _ in headings}
    preamble_sections, preamble_anchors, preamble_ids = _detect_preamble_sections(
        pages,
        heading_positions,
        campaign_id=campaign_id,
        document_id=document_id,
    )

    if preamble_sections:
        merged_sections: list[SectionRecord] = []
        merged_anchors: list[tuple[int, int]] = []
        preamble_index = 0
        for section, anchor in zip(sections, anchors, strict=True):
            while (
                preamble_index < len(preamble_sections)
                and (
                    preamble_anchors[preamble_index][0] < anchor[0]
                    or (
                        preamble_anchors[preamble_index][0] == anchor[0]
                        and preamble_anchors[preamble_index][1] < anchor[1]
                    )
                )
            ):
                merged_sections.append(preamble_sections[preamble_index])
                merged_anchors.append(preamble_anchors[preamble_index])
                preamble_index += 1
            merged_sections.append(section)
            merged_anchors.append(anchor)
        while preamble_index < len(preamble_sections):
            merged_sections.append(preamble_sections[preamble_index])
            merged_anchors.append(preamble_anchors[preamble_index])
            preamble_index += 1
        sections = merged_sections
        anchors = merged_anchors
        content_only_ids = preamble_ids
    else:
        content_only_ids = frozenset()

    return SectionDetectionResult(
        sections=sections,
        heading_anchors=anchors,
        content_only_section_ids=content_only_ids,
    )
