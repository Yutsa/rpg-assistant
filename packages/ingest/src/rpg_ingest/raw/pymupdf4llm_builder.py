from __future__ import annotations

import re
from dataclasses import dataclass

from rpg_ingest.raw.chunking import (
    DEFAULT_MAX_TOKENS,
    _finalize_chunks,
    _group_blocks_for_chunking,
    _make_chunk,
)
from rpg_ingest.raw.layout import LayoutBlock, LayoutPage
from rpg_ingest.raw.pymupdf4llm_extractor import ExtractedElement
from rpg_ingest.raw.reading_order import is_meta_box_heading, normalize_section_title
from rpg_ingest.raw.sections import (
    CHAPTER_RE,
    NUMBERED_HEADING_RE,
    SectionDetectionResult,
    refine_section_page_ends,
)
from rpg_ingest.raw.stat_blocks.profile import StatBlockProfile
from rpg_ingest.raw.stat_blocks.types import StatBlockSpan
from rpg_core.models.raw import ChunkRecord, SectionRecord
from rpg_core.storage.ids import new_id


@dataclass(frozen=True)
class _OpenSection:
    section_index: int
    level: int


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


def _find_page(pages: list[LayoutPage], page_number: int) -> LayoutPage | None:
    return next((page for page in pages if page.page_number == page_number), None)


PARTIE_RE = re.compile(r"^partie\s+[ivxlc\d]+\b", re.IGNORECASE)


def _resolve_heading_level(element: ExtractedElement) -> int:
    text = element.text.strip()
    markdown_level = max(1, min(element.level or 1, 6))
    if CHAPTER_RE.match(text) or PARTIE_RE.match(text):
        return 1
    if is_meta_box_heading(text):
        return 2
    numbered = NUMBERED_HEADING_RE.match(text)
    if numbered:
        dots = numbered.group(1).count(".")
        return min(6, 2 if dots <= 1 else dots + 1)
    return markdown_level


def _normalize_heading_levels(headings: list[ExtractedElement]) -> None:
    if not headings:
        return
    resolved = [_resolve_heading_level(heading) for heading in headings]
    min_level = min(resolved)
    if min_level > 1:
        resolved = [level - min_level + 1 for level in resolved]
    for heading, level in zip(headings, resolved, strict=True):
        heading.level = level


def build_sections_from_elements(
    elements: list[ExtractedElement],
    *,
    campaign_id: str,
    document_id: str,
    page_count: int,
    profile: StatBlockProfile | None = None,
) -> SectionDetectionResult:
    headings = [element for element in elements if element.kind == "heading"]
    _normalize_heading_levels(headings)
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
                    page_end=max(page_count, 1),
                )
            ],
            heading_anchors=[],
        )

    sections: list[SectionRecord] = []
    heading_anchors: list[tuple[int, int]] = []
    stack: list[_OpenSection] = []
    section_ids: list[str] = []

    for heading in headings:
        level = max(1, min(heading.level or 1, 6))
        while stack and stack[-1].level >= level:
            stack.pop()

        parent_section_id = (
            section_ids[stack[-1].section_index] if stack else None
        )
        section_id = new_id("sec")
        section_index = len(sections)
        title = normalize_section_title(heading.text)
        sections.append(
            SectionRecord(
                id=section_id,
                campaign_id=campaign_id,
                document_id=document_id,
                parent_section_id=parent_section_id,
                title=title,
                level=level,
                page_start=heading.page,
                page_end=page_count,
            )
        )
        section_ids.append(section_id)
        heading_anchors.append((heading.page, heading.block_index))
        stack.append(_OpenSection(section_index=section_index, level=level))

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
    )


def _assign_elements_to_sections(
    elements: list[ExtractedElement],
    sections: list[SectionRecord],
    heading_anchors: list[tuple[int, int]],
    pages: list[LayoutPage],
) -> list[list[tuple[LayoutPage, LayoutBlock]]]:
    if not sections:
        return []

    if len(sections) == 1 and sections[0].title == "Document":
        block_items: list[tuple[LayoutPage, LayoutBlock]] = []
        for element in elements:
            page = _find_page(pages, element.page)
            block = _find_block(pages, element.page, element.block_index)
            if page is None or block is None:
                continue
            block_items.append((page, block))
        return [block_items]

    heading_positions = set(heading_anchors)
    anchor_to_section = {
        anchor: section.id
        for anchor, section in zip(heading_anchors, sections, strict=True)
    }

    section_blocks: list[list[tuple[LayoutPage, LayoutBlock]]] = [
        [] for _ in sections
    ]
    section_id_to_index = {section.id: index for index, section in enumerate(sections)}

    stack: list[_OpenSection] = []
    current_section_index: int | None = None

    for element in elements:
        position = (element.page, element.block_index)
        if element.kind == "heading" and position in heading_positions:
            level = max(1, min(element.level or 1, 6))
            while stack and stack[-1].level >= level:
                stack.pop()
            section_id = anchor_to_section[position]
            current_section_index = section_id_to_index[section_id]
            stack.append(
                _OpenSection(section_index=current_section_index, level=level)
            )
            continue

        if current_section_index is None:
            continue

        page = _find_page(pages, element.page)
        block = _find_block(pages, element.page, element.block_index)
        if page is None or block is None:
            continue
        section_blocks[current_section_index].append((page, block))

    return section_blocks


def build_chunks_from_elements(
    elements: list[ExtractedElement],
    section_result: SectionDetectionResult,
    pages: list[LayoutPage],
    *,
    campaign_id: str,
    document_id: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    stat_spans: list[StatBlockSpan] | None = None,
    profile: StatBlockProfile | None = None,
) -> list[ChunkRecord]:
    """Assign ordered elements to sections and build chunks."""
    if not pages:
        return []

    span_by_id = {span.id: span for span in (stat_spans or [])}
    sections = section_result.sections
    heading_anchors = section_result.heading_anchors
    section_blocks = _assign_elements_to_sections(
        elements,
        sections,
        heading_anchors,
        pages,
    )

    chunks: list[ChunkRecord] = []
    chunk_index = 0

    if len(sections) == 1 and sections[0].title == "Document":
        groups = _group_blocks_for_chunking(
            section_blocks[0],
            max_tokens,
            None,
        )
        for group in groups:
            chunks.append(
                _make_chunk(
                    campaign_id=campaign_id,
                    document_id=document_id,
                    section_id=sections[0].id,
                    index=chunk_index,
                    block_groups=group,
                    needs_rechunk=len(group) < 2,
                    profile=profile,
                    stat_spans=span_by_id,
                )
            )
            chunk_index += 1
        return _finalize_chunks(chunks, pages, sections)

    for section_index, section in enumerate(sections):
        block_items = section_blocks[section_index]
        if not block_items:
            continue
        groups = _group_blocks_for_chunking(
            block_items,
            max_tokens,
            None,
            pages=pages,
        )
        for group in groups:
            chunks.append(
                _make_chunk(
                    campaign_id=campaign_id,
                    document_id=document_id,
                    section_id=section.id,
                    index=chunk_index,
                    block_groups=group,
                    needs_rechunk=len(groups) == 1 and len(group) > 40,
                    profile=profile,
                    stat_spans=span_by_id,
                )
            )
            chunk_index += 1

    refined_sections = list(sections)
    refine_section_page_ends(refined_sections, chunks)
    return _finalize_chunks(chunks, pages, refined_sections)


def refresh_element_kinds_from_layout(
    elements: list[ExtractedElement],
    pages: list[LayoutPage],
) -> None:
    """Sync element kinds with post-processed layout metadata (stat blocks)."""
    for element in elements:
        block = _find_block(pages, element.page, element.block_index)
        if block is None:
            continue
        if block.metadata.get("stat_block_id"):
            element.kind = "stat_block_candidate"
            element.metadata.update(block.metadata)
