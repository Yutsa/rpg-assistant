from __future__ import annotations

import re

import tiktoken

from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage, merge_block_bboxes
from rpg_assistant.ingestion.raw.stat_blocks.profile import StatBlockProfile
from rpg_assistant.ingestion.raw.stat_blocks.types import StatBlockSpan
from rpg_assistant.models.raw import ChunkRecord, SectionRecord, SourceSpan
from rpg_assistant.storage.ids import chunk_id, page_block_id

DEFAULT_MAX_TOKENS = 1200
ENCODING_NAME = "cl100k_base"


def _get_encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(ENCODING_NAME)


def estimate_tokens(text: str) -> int:
    return len(_get_encoding().encode(text))


def _chunk_type_hint(
    text: str,
    blocks: list[LayoutBlock],
    *,
    profile: StatBlockProfile | None = None,
) -> str:
    if profile:
        hinted = profile.chunk_type_hint(text, blocks)
        if hinted:
            return hinted
    lowered = text.lower()
    if "secret" in lowered or "gm only" in lowered:
        return "secret"
    if "clue" in lowered:
        return "clue"
    if "handout" in lowered:
        return "handout"
    if "map" in lowered[:200]:
        return "map"
    return "lore"


def _block_position(page_number: int, block_index: int) -> tuple[int, int]:
    return (page_number, block_index)


def _blocks_for_page_range(
    pages: list[LayoutPage], page_start: int, page_end: int
) -> list[tuple[LayoutPage, LayoutBlock]]:
    result: list[tuple[LayoutPage, LayoutBlock]] = []
    for page in pages:
        if page.page_number < page_start or page.page_number > page_end:
            continue
        for block in page.blocks:
            result.append((page, block))
    return result


def _blocks_for_section_content(
    pages: list[LayoutPage],
    heading_anchor: tuple[int, int],
    next_heading_anchor: tuple[int, int] | None,
) -> list[tuple[LayoutPage, LayoutBlock]]:
    """Return content blocks strictly between two heading anchors."""
    result: list[tuple[LayoutPage, LayoutBlock]] = []
    for page in pages:
        for block in page.blocks:
            pos = _block_position(page.page_number, block.block_index)
            if pos <= heading_anchor:
                continue
            if next_heading_anchor is not None and pos >= next_heading_anchor:
                continue
            result.append((page, block))
    return result


def chunk_block_signature(chunk: ChunkRecord) -> frozenset[str]:
    block_ids: list[str] = []
    for span in chunk.source_spans:
        block_ids.extend(span.page_block_ids)
    return frozenset(block_ids)


def chunk_uniqueness_stats(chunks: list[ChunkRecord]) -> dict[str, float | int]:
    if not chunks:
        return {
            "chunk_unique_block_signature_count": 0,
            "duplicate_chunk_count": 0,
            "chunk_unique_block_signature_ratio": 1.0,
        }
    signatures = [chunk_block_signature(chunk) for chunk in chunks]
    unique_count = len(set(signatures))
    return {
        "chunk_unique_block_signature_count": unique_count,
        "duplicate_chunk_count": len(chunks) - unique_count,
        "chunk_unique_block_signature_ratio": unique_count / len(chunks),
    }


def _partition_by_stat_boundaries(
    block_items: list[tuple[LayoutPage, LayoutBlock]],
) -> list[tuple[str | None, list[tuple[LayoutPage, LayoutBlock]]]]:
    groups: list[tuple[str | None, list[tuple[LayoutPage, LayoutBlock]]]] = []
    current: list[tuple[LayoutPage, LayoutBlock]] = []
    current_stat_id: str | None = None

    for page, block in block_items:
        stat_id = block.metadata.get("stat_block_id")
        if current and stat_id != current_stat_id:
            groups.append((current_stat_id, current))
            current = []
        current_stat_id = stat_id
        current.append((page, block))

    if current:
        groups.append((current_stat_id, current))
    return groups


def _split_blocks_into_chunks(
    block_items: list[tuple[LayoutPage, LayoutBlock]],
    max_tokens: int,
) -> list[list[tuple[LayoutPage, LayoutBlock]]]:
    chunks: list[list[tuple[LayoutPage, LayoutBlock]]] = []
    current: list[tuple[LayoutPage, LayoutBlock]] = []
    current_tokens = 0

    for page, block in block_items:
        block_tokens = estimate_tokens(block.text)
        if current and current_tokens + block_tokens > max_tokens:
            chunks.append(current)
            current = []
            current_tokens = 0
        current.append((page, block))
        current_tokens += block_tokens

    if current:
        chunks.append(current)
    return chunks


def _group_blocks_for_chunking(
    block_items: list[tuple[LayoutPage, LayoutBlock]],
    max_tokens: int,
) -> list[list[tuple[LayoutPage, LayoutBlock]]]:
    groups: list[list[tuple[LayoutPage, LayoutBlock]]] = []
    for stat_id, stat_group in _partition_by_stat_boundaries(block_items):
        if stat_id:
            groups.append(stat_group)
        else:
            groups.extend(_split_blocks_into_chunks(stat_group, max_tokens))
    return groups


def _make_chunk(
    *,
    campaign_id: str,
    document_id: str,
    section_id: str | None,
    index: int,
    block_groups: list[tuple[LayoutPage, LayoutBlock]],
    needs_rechunk: bool = False,
    profile: StatBlockProfile | None = None,
    stat_spans: dict[str, StatBlockSpan] | None = None,
) -> ChunkRecord:
    blocks_only = [b for _, b in block_groups]
    stat_id = blocks_only[0].metadata.get("stat_block_id") if blocks_only else None
    metadata: dict = {}
    text: str

    if stat_id and profile and stat_spans and stat_id in stat_spans:
        parsed = profile.parse_span(stat_spans[stat_id])
        text = parsed.raw_text or "\n\n".join(
            profile.normalize_block_text(block.text) for _, block in block_groups
        )
        metadata = {
            "stat_block": parsed.model_dump(),
            "game_system": parsed.game_system,
        }
        chunk_hint = "stat_block"
    else:
        text = "\n\n".join(block.text for _, block in block_groups)
        chunk_hint = _chunk_type_hint(text, blocks_only, profile=profile)

    page_numbers = [page.page_number for page, _ in block_groups]
    page_start = min(page_numbers)
    page_end = max(page_numbers)

    spans_by_page: dict[int, list[LayoutBlock]] = {}
    for page, block in block_groups:
        spans_by_page.setdefault(page.page_number, []).append(block)

    source_spans: list[SourceSpan] = []
    for page_num in sorted(spans_by_page):
        page_blocks = spans_by_page[page_num]
        source_spans.append(
            SourceSpan(
                page=page_num,
                page_block_ids=[
                    page_block_id(page_num, b.block_index) for b in page_blocks
                ],
                bbox=merge_block_bboxes(page_blocks),
            )
        )

    return ChunkRecord(
        id=chunk_id(page_start, index),
        campaign_id=campaign_id,
        document_id=document_id,
        section_id=section_id,
        page_start=page_start,
        page_end=page_end,
        text=text,
        chunk_type_hint=chunk_hint,
        token_count=estimate_tokens(text),
        source_spans=source_spans,
        metadata=metadata,
        needs_rechunk=needs_rechunk,
    )


def build_chunks(
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
    if not pages:
        return []

    span_by_id = {span.id: span for span in (stat_spans or [])}
    chunks: list[ChunkRecord] = []
    chunk_index = 0

    if len(sections) <= 1 and sections[0].title == "Document":
        block_items = _blocks_for_page_range(
            pages, sections[0].page_start, sections[0].page_end
        )
        for group in _group_blocks_for_chunking(block_items, max_tokens):
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
        return chunks

    use_anchors = (
        heading_anchors is not None and len(heading_anchors) == len(sections)
    )

    for section_index, section in enumerate(sections):
        if use_anchors:
            anchor = heading_anchors[section_index]
            next_anchor = (
                heading_anchors[section_index + 1]
                if section_index + 1 < len(heading_anchors)
                else None
            )
            block_items = _blocks_for_section_content(pages, anchor, next_anchor)
        else:
            block_items = _blocks_for_page_range(
                pages, section.page_start, section.page_end
            )
        if not block_items:
            continue
        groups = _group_blocks_for_chunking(block_items, max_tokens)
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

    return chunks
