"""Chunk building from Docling reading order."""

from __future__ import annotations

from rpg_ingest.raw.chunking import (
    DEFAULT_MAX_TOKENS,
    _finalize_chunks,
    _group_blocks_for_chunking,
    _make_chunk,
)
from rpg_ingest.raw.elements import DocElement
from rpg_ingest.raw.layout import LayoutBlock, LayoutPage
from rpg_ingest.raw.stat_blocks.profile import StatBlockProfile
from rpg_ingest.raw.stat_blocks.types import StatBlockSpan
from rpg_core.models.raw import ChunkRecord, SectionRecord


def _pages_by_number(pages: list[LayoutPage]) -> dict[int, LayoutPage]:
    return {page.page_number: page for page in pages}


def _resolve_block(
    element: DocElement,
    pages_by_number: dict[int, LayoutPage],
) -> tuple[LayoutPage, LayoutBlock] | None:
    page = pages_by_number.get(element.page_number)
    if page is None or element.block_index >= len(page.blocks):
        return None
    return page, page.blocks[element.block_index]


def _is_section_heading(
    element: DocElement,
    block: LayoutBlock,
    page_blocks: list[LayoutBlock],
    *,
    profile: StatBlockProfile | None,
) -> bool:
    if not element.is_heading:
        return False
    if block.metadata.get("stat_block_role") in {"header", "stats", "icon"}:
        return False
    if profile and profile.is_false_heading(block, page_blocks, element.block_index):
        return False
    return True


def _is_chunk_content(
    element: DocElement,
    block: LayoutBlock,
    page_blocks: list[LayoutBlock],
    *,
    profile: StatBlockProfile | None,
) -> bool:
    if element.is_skipped:
        return False
    if element.is_content:
        return True
    if block.metadata.get("stat_block_id"):
        return True
    if element.is_heading and profile and profile.is_false_heading(
        block, page_blocks, element.block_index
    ):
        return True
    return False


def build_chunks_from_elements(
    elements: list[DocElement],
    pages: list[LayoutPage],
    sections: list[SectionRecord],
    *,
    campaign_id: str,
    document_id: str,
    heading_anchors: list[tuple[int, int]] | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    stat_spans: list[StatBlockSpan] | None = None,
    profile: StatBlockProfile | None = None,
) -> list[ChunkRecord]:
    """Build chunks by walking Docling elements in reading order."""
    pages_by_number = _pages_by_number(pages)
    span_by_id = {span.id: span for span in (stat_spans or [])}

    if not sections:
        return []

    # Fallback: single Document section without anchors
    if not heading_anchors:
        block_items: list[tuple[LayoutPage, LayoutBlock]] = []
        for element in elements:
            located = _resolve_block(element, pages_by_number)
            if located is None:
                continue
            page, block = located
            if not _is_chunk_content(
                element, block, page.blocks, profile=profile
            ):
                continue
            block_items.append((page, block))
        chunks: list[ChunkRecord] = []
        chunk_index = 0
        for group in _group_blocks_for_chunking(block_items, max_tokens, pages=pages):
            chunks.append(
                _make_chunk(
                    campaign_id=campaign_id,
                    document_id=document_id,
                    section_id=sections[0].id,
                    index=chunk_index,
                    block_groups=group,
                    profile=profile,
                    stat_spans=span_by_id,
                )
            )
            chunk_index += 1
        return _finalize_chunks(chunks, pages, sections)

    anchor_to_section = {
        anchor: section.id
        for anchor, section in zip(heading_anchors, sections, strict=True)
    }
    section_blocks: dict[str, list[tuple[LayoutPage, LayoutBlock]]] = {
        section.id: [] for section in sections
    }
    current_section_id = sections[0].id

    for element in elements:
        if element.is_skipped:
            continue
        located = _resolve_block(element, pages_by_number)
        if located is None:
            continue
        page, block = located
        if _is_section_heading(element, block, page.blocks, profile=profile):
            section_id = anchor_to_section.get(element.position)
            if section_id:
                current_section_id = section_id
            continue
        if not _is_chunk_content(element, block, page.blocks, profile=profile):
            continue
        section_blocks[current_section_id].append((page, block))

    chunks = []
    chunk_index = 0
    for section in sections:
        block_items = section_blocks.get(section.id, [])
        if not block_items:
            continue
        groups = _group_blocks_for_chunking(block_items, max_tokens, pages=pages)
        for group in groups:
            chunks.append(
                _make_chunk(
                    campaign_id=campaign_id,
                    document_id=document_id,
                    section_id=section.id,
                    index=chunk_index,
                    block_groups=group,
                    profile=profile,
                    stat_spans=span_by_id,
                )
            )
            chunk_index += 1

    return _finalize_chunks(chunks, pages, sections)
