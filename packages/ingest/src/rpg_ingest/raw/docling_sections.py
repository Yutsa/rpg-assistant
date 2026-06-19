"""Section detection from Docling-structured elements."""

from __future__ import annotations

from rpg_ingest.raw.elements import DocElement
from rpg_ingest.raw.layout import LayoutBlock, LayoutPage
from rpg_ingest.raw.sections import SectionDetectionResult
from rpg_ingest.raw.stat_blocks.profile import StatBlockProfile
from rpg_core.models.raw import SectionRecord
from rpg_core.storage.ids import new_id


def _block_for_element(
    pages: list[LayoutPage],
    element: DocElement,
) -> tuple[LayoutPage, object] | None:
    page = next((p for p in pages if p.page_number == element.page_number), None)
    if page is None:
        return None
    if element.block_index >= len(page.blocks):
        return None
    return page, page.blocks[element.block_index]


def _is_excluded_heading_block(
    block: LayoutBlock,
    page_blocks: list[LayoutBlock],
    block_idx: int,
    *,
    profile: StatBlockProfile | None,
) -> bool:
    role = block.metadata.get("stat_block_role")
    if role in {"header", "stats", "icon"}:
        return True
    if profile and profile.is_false_heading(block, page_blocks, block_idx):
        return True
    for offset in range(1, 3):
        next_idx = block_idx + offset
        if next_idx >= len(page_blocks):
            break
        nxt = page_blocks[next_idx]
        if nxt.metadata.get("stat_block_role") in {"header", "stats"}:
            return True
        if " | NC " in nxt.text and block.text.strip() in nxt.text:
            return True
    return False


def detect_sections_from_elements(
    elements: list[DocElement],
    pages: list[LayoutPage],
    *,
    campaign_id: str,
    document_id: str,
    profile: StatBlockProfile | None = None,
) -> SectionDetectionResult:
    """Build section hierarchy from Docling heading levels and reading order."""
    headings: list[DocElement] = []
    for element in elements:
        if not element.is_heading:
            continue
        if profile:
            located = _block_for_element(pages, element)
            if located:
                page, block = located
                page_blocks = page.blocks
                block_idx = element.block_index
                if _is_excluded_heading_block(
                    block, page_blocks, block_idx, profile=profile
                ):
                    continue
        headings.append(element)

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

    page_end = pages[-1].page_number if pages else 1
    sections: list[SectionRecord] = []
    anchors: list[tuple[int, int]] = []
    stack: list[tuple[int, str]] = []

    for index, heading in enumerate(headings):
        level = heading.heading_level or 1
        title = heading.text.strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent_id = stack[-1][1] if stack else None

        section_id = new_id("sec")
        page_end_for_section = (
            headings[index + 1].page_number - 1
            if index + 1 < len(headings)
            else page_end
        )
        if page_end_for_section < heading.page_number:
            page_end_for_section = heading.page_number

        sections.append(
            SectionRecord(
                id=section_id,
                campaign_id=campaign_id,
                document_id=document_id,
                parent_section_id=parent_id,
                title=title,
                level=level,
                page_start=heading.page_number,
                page_end=page_end_for_section,
            )
        )
        anchors.append((heading.page_number, heading.block_index))
        stack.append((level, section_id))

    return SectionDetectionResult(
        sections=sections,
        heading_anchors=anchors,
        content_only_section_ids=frozenset(),
    )
