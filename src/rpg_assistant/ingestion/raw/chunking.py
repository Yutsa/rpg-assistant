from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage, merge_block_bboxes
from rpg_assistant.ingestion.raw.reading_order import (
    find_block,
    is_in_heading_content_zone,
    page_is_sparse,
    spatial_sort_key,
)
from rpg_assistant.ingestion.raw.stat_blocks.profile import StatBlockProfile
from rpg_assistant.ingestion.raw.stat_blocks.types import StatBlockSpan
from rpg_assistant.models.raw import ChunkRecord, SectionRecord, SourceSpan
from rpg_assistant.storage.ids import chunk_id, page_block_id

DEFAULT_MAX_TOKENS = 1200
ENCODING_NAME = "cl100k_base"


@dataclass(frozen=True)
class _HeadingRef:
    section_index: int
    page_number: int
    block_index: int
    block: LayoutBlock
    title: str
    is_content_only: bool


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


def _first_heading_y_on_page(
    page: LayoutPage, heading_positions: set[tuple[int, int]]
) -> float | None:
    ys = [
        block.bbox.y0
        for block in page.blocks
        if (page.page_number, block.block_index) in heading_positions
    ]
    return min(ys) if ys else None


def _intervening_heading_blocks(
    heading: LayoutBlock,
    block: LayoutBlock,
    page: LayoutPage,
    heading_refs: list[_HeadingRef],
) -> list[LayoutBlock]:
    between: list[LayoutBlock] = []
    for ref in heading_refs:
        if ref.page_number != page.page_number:
            continue
        if ref.block_index == heading.block_index and ref.page_number == heading.page_number:
            continue
        other = ref.block
        if other.bbox.y0 <= heading.bbox.y0:
            continue
        if other.bbox.y0 >= block.bbox.y0:
            continue
        if is_in_heading_content_zone(block, other, heading_text=ref.title):
            between.append(other)
    return between


def _gap_pages_between(
    pages: list[LayoutPage], from_page: int, to_page: int
) -> list[LayoutPage]:
    return [
        page
        for page in pages
        if from_page < page.page_number < to_page and page_is_sparse(page)
    ]


def _last_text_page_before(
    pages: list[LayoutPage], page_number: int
) -> int | None:
    probe = page_number - 1
    while probe >= 1:
        page = next((p for p in pages if p.page_number == probe), None)
        if page is None:
            return None
        if page_is_sparse(page):
            probe -= 1
            continue
        return probe
    return None


def _blocks_for_section_spatial(
    pages: list[LayoutPage],
    heading_ref: _HeadingRef,
    heading_refs: list[_HeadingRef],
    heading_positions: set[tuple[int, int]],
    *,
    continuation_by_page: dict[int, int | None],
    claimed: set[tuple[int, int]] | None = None,
) -> list[tuple[LayoutPage, LayoutBlock]]:
    heading = heading_ref.block
    result: list[tuple[LayoutPage, LayoutBlock]] = []
    taken = claimed or set()

    for page in pages:
        if page.page_number < heading_ref.page_number:
            continue
        for block in page.blocks:
            pos = (page.page_number, block.block_index)
            if pos in taken:
                continue
            if (
                heading_ref.is_content_only
                and pos == (heading_ref.page_number, heading_ref.block_index)
            ):
                result.append((page, block))
                continue
            if pos in heading_positions:
                continue

            if page.page_number == heading_ref.page_number:
                if not heading_ref.is_content_only and block.bbox.y0 <= heading.bbox.y0:
                    continue
                if not is_in_heading_content_zone(
                    block, heading, heading_text=heading_ref.title
                ):
                    continue
                if _intervening_heading_blocks(heading, block, page, heading_refs):
                    continue
            else:
                last_text_page = _last_text_page_before(pages, page.page_number)
                gap_pages = (
                    _gap_pages_between(pages, last_text_page, page.page_number)
                    if last_text_page is not None
                    else []
                )
                first_heading_y = _first_heading_y_on_page(page, heading_positions)
                is_continuation = (
                    continuation_by_page.get(page.page_number) == heading_ref.section_index
                    and bool(gap_pages)
                    and (first_heading_y is None or block.bbox.y0 < first_heading_y)
                )
                if not is_continuation:
                    continue

            result.append((page, block))

    result.sort(key=lambda item: spatial_sort_key(item[1]))
    return result


def _nearest_heading_ref(
    block: LayoutBlock,
    heading_refs: list[_HeadingRef],
) -> _HeadingRef | None:
    block_key = spatial_sort_key(block)
    best: _HeadingRef | None = None
    best_key: tuple[int, float, float] | None = None
    for ref in heading_refs:
        ref_key = spatial_sort_key(ref.block)
        if ref_key > block_key:
            continue
        if best is None or ref_key > best_key:
            best = ref
            best_key = ref_key
    return best


def _assign_orphan_blocks(
    pages: list[LayoutPage],
    section_blocks: list[list[tuple[LayoutPage, LayoutBlock]]],
    heading_refs: list[_HeadingRef],
    heading_positions: set[tuple[int, int]],
    claimed: set[tuple[int, int]],
) -> None:
    for page in pages:
        for block in page.blocks:
            pos = (page.page_number, block.block_index)
            if pos in claimed or pos in heading_positions:
                continue
            nearest = _nearest_heading_ref(block, heading_refs)
            if nearest is None:
                continue
            section_blocks[nearest.section_index].append((page, block))
            claimed.add(pos)


def _continuation_owner_by_page(
    pages: list[LayoutPage],
    section_blocks: list[list[tuple[LayoutPage, LayoutBlock]]],
) -> dict[int, int | None]:
    owners: dict[int, int | None] = {}
    for page in pages:
        if page_is_sparse(page):
            continue
        last_text_page = _last_text_page_before(pages, page.page_number)
        if last_text_page is None:
            continue
        gap_pages = _gap_pages_between(pages, last_text_page, page.page_number)
        if not gap_pages:
            continue

        best_index: int | None = None
        best_y = -1.0
        for section_index, block_items in enumerate(section_blocks):
            prev_blocks = [
                block for pg, block in block_items if pg.page_number == last_text_page
            ]
            if not prev_blocks:
                continue
            last_y = max(block.bbox.y1 for block in prev_blocks)
            if last_y > best_y:
                best_y = last_y
                best_index = section_index
        owners[page.page_number] = best_index

    return owners


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
    content_only_section_ids: frozenset[str] | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    stat_spans: list[StatBlockSpan] | None = None,
    profile: StatBlockProfile | None = None,
) -> list[ChunkRecord]:
    if not pages:
        return []

    span_by_id = {span.id: span for span in (stat_spans or [])}
    chunks: list[ChunkRecord] = []
    chunk_index = 0
    content_only = content_only_section_ids or frozenset()

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

    if not use_anchors:
        for section in sections:
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

    heading_positions = set(heading_anchors)
    heading_refs: list[_HeadingRef] = []
    for section_index, (page_num, block_idx) in enumerate(heading_anchors):
        block = find_block(pages, page_num, block_idx)
        if block is None:
            continue
        heading_refs.append(
            _HeadingRef(
                section_index=section_index,
                page_number=page_num,
                block_index=block_idx,
                block=block,
                title=sections[section_index].title,
                is_content_only=sections[section_index].id in content_only,
            )
        )

    section_blocks: list[list[tuple[LayoutPage, LayoutBlock]]] = [[] for _ in sections]
    claimed: set[tuple[int, int]] = set()
    sorted_refs = sorted(heading_refs, key=lambda ref: spatial_sort_key(ref.block))

    for ref in sorted_refs:
        same_page_blocks = _blocks_for_section_spatial(
            pages,
            ref,
            heading_refs,
            heading_positions,
            continuation_by_page={},
            claimed=claimed,
        )
        section_blocks[ref.section_index].extend(same_page_blocks)
        for page, block in same_page_blocks:
            claimed.add((page.page_number, block.block_index))

    continuation_by_page = _continuation_owner_by_page(pages, section_blocks)
    for ref in sorted_refs:
        continuation_blocks = _blocks_for_section_spatial(
            pages,
            ref,
            heading_refs,
            heading_positions,
            continuation_by_page=continuation_by_page,
            claimed=claimed,
        )
        section_blocks[ref.section_index].extend(continuation_blocks)
        for page, block in continuation_blocks:
            claimed.add((page.page_number, block.block_index))

    _assign_orphan_blocks(
        pages, section_blocks, heading_refs, heading_positions, claimed
    )
    for block_items in section_blocks:
        block_items.sort(key=lambda item: spatial_sort_key(item[1]))

    for section_index, section in enumerate(sections):
        block_items = section_blocks[section_index]
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
