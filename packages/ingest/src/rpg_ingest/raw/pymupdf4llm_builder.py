from __future__ import annotations

import re

from rpg_ingest.raw.chunking import DEFAULT_MAX_TOKENS, build_chunks
from rpg_ingest.raw.elements import DocElement
from rpg_ingest.raw.layout import LayoutBlock, LayoutPage
from rpg_ingest.raw.reading_order import (
    is_chapter_heading,
    is_meta_box_heading,
    normalize_section_title,
)
from rpg_ingest.raw.sections import (
    CHAPTER_RE,
    NUMBERED_HEADING_RE,
    SectionDetectionResult,
    _reparent_same_page_subordinates,
)
from rpg_ingest.raw.stat_blocks.profile import StatBlockProfile
from rpg_ingest.raw.stat_blocks.types import StatBlockSpan
from rpg_core.models.raw import ChunkRecord, SectionRecord
from rpg_core.storage.ids import new_id

PARTIE_RE = re.compile(r"^partie\s+[ivxlc\d]+\b", re.IGNORECASE)


def _find_block(
    pages: list[LayoutPage], page_number: int, block_index: int
) -> LayoutBlock | None:
    for page in pages:
        if page.page_number != page_number:
            continue
        for block in page.blocks:
            if block.block_index == block_index:
                return block
    return None


def _resolve_heading_level(element: DocElement) -> int:
    text = element.text.strip()
    markdown_level = max(1, min(element.heading_level or 1, 6))
    if CHAPTER_RE.match(text) or PARTIE_RE.match(text):
        return 1
    if is_meta_box_heading(text):
        return 2
    numbered = NUMBERED_HEADING_RE.match(text)
    if numbered:
        dots = numbered.group(1).count(".")
        return min(6, 2 if dots <= 1 else dots + 1)
    return markdown_level


def _normalize_heading_levels(headings: list[DocElement]) -> None:
    if not headings:
        return
    resolved = [_resolve_heading_level(heading) for heading in headings]
    min_level = min(resolved)
    if min_level > 1:
        resolved = [level - min_level + 1 for level in resolved]
    for heading, level in zip(headings, resolved, strict=True):
        heading.heading_level = level


def build_sections_from_elements(
    elements: list[DocElement],
    pages: list[LayoutPage],
    *,
    campaign_id: str,
    document_id: str,
    profile: StatBlockProfile | None = None,
) -> SectionDetectionResult:
    headings = [element for element in elements if element.is_heading]
    _normalize_heading_levels(headings)
    page_count = max((page.page_number for page in pages), default=1)

    if not headings:
        return SectionDetectionResult(
            sections=[
                SectionRecord(
                    id=new_id("sec"),
                    campaign_id=campaign_id,
                    document_id=document_id,
                    parent_section_id=None,
                    title="Document",
                    level=1,
                    page_start=1,
                    page_end=page_count,
                )
            ],
            heading_anchors=[],
        )

    sections: list[SectionRecord] = []
    heading_anchors: list[tuple[int, int]] = []
    stack: list[tuple[int, int]] = []
    section_ids: list[str] = []
    subordinate_section_ids: list[str] = []
    active_chapter_id: str | None = None

    for heading in headings:
        level = max(1, min(heading.heading_level or 1, 6))
        while stack and stack[-1][1] >= level:
            stack.pop()

        parent_section_id = section_ids[stack[-1][0]] if stack else None
        section_id = new_id("sec")
        section_index = len(sections)
        title = normalize_section_title(heading.text)
        is_chapter = is_chapter_heading(title) or PARTIE_RE.match(title) is not None

        sections.append(
            SectionRecord(
                id=section_id,
                campaign_id=campaign_id,
                document_id=document_id,
                parent_section_id=parent_section_id,
                title=title,
                level=level,
                page_start=heading.page_number,
                page_end=page_count,
            )
        )
        section_ids.append(section_id)
        heading_anchors.append(heading.position)

        if is_chapter and level == 1:
            active_chapter_id = section_id
            _reparent_same_page_subordinates(
                sections,
                chapter_section_id=section_id,
                chapter_page=heading.page_number,
                subordinate_section_ids=frozenset(subordinate_section_ids),
            )
            subordinate_section_ids.clear()
        elif level >= 2 and parent_section_id is None and active_chapter_id:
            sections[-1].parent_section_id = active_chapter_id
            sections[-1].level = 2
            subordinate_section_ids.append(section_id)

        stack.append((section_index, sections[-1].level))

    for index, section in enumerate(sections):
        next_same_or_higher_page = page_count
        for later in sections[index + 1 :]:
            if later.level <= section.level:
                next_same_or_higher_page = later.page_start
                break
        section.page_end = max(section.page_start, next_same_or_higher_page)

    return SectionDetectionResult(
        sections=sections,
        heading_anchors=heading_anchors,
        content_only_section_ids=frozenset(),
    )


def build_chunks_from_elements(
    elements: list[DocElement],
    pages: list[LayoutPage],
    sections: list[SectionRecord],
    *,
    campaign_id: str,
    document_id: str,
    heading_anchors: list[tuple[int, int]] | None = None,
    content_only_section_ids: frozenset[str] | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    stat_spans: list[StatBlockSpan] | None = None,
    profile: StatBlockProfile | None = None,
) -> list[ChunkRecord]:
    """Build chunks via legacy spatial assignment using PyMuPDF4LLM section anchors."""
    _ = elements
    return build_chunks(
        pages,
        sections,
        campaign_id=campaign_id,
        document_id=document_id,
        heading_anchors=heading_anchors,
        content_only_section_ids=content_only_section_ids,
        max_tokens=max_tokens,
        stat_spans=stat_spans,
        profile=profile,
    )


def refresh_element_kinds_from_layout(
    elements: list[DocElement],
    pages: list[LayoutPage],
) -> None:
    """Sync element metadata with post-processed layout (stat blocks)."""
    for element in elements:
        block = _find_block(pages, element.page_number, element.block_index)
        if block is None:
            continue
        if block.metadata.get("stat_block_id"):
            element.metadata.update(block.metadata)
