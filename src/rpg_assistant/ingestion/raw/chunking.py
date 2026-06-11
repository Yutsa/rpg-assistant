from __future__ import annotations

import re

import tiktoken

from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage, merge_block_bboxes
from rpg_assistant.models.raw import ChunkRecord, SectionRecord, SourceSpan
from rpg_assistant.storage.ids import chunk_id, page_block_id

DEFAULT_MAX_TOKENS = 1200
ENCODING_NAME = "cl100k_base"

TABLE_RE = re.compile(r"(\|.+\|)|(\bAC\b|\bHP\b|\bSpeed\b)", re.IGNORECASE)
STAT_BLOCK_RE = re.compile(r"\b(armor class|hit points|challenge rating)\b", re.IGNORECASE)


def _get_encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(ENCODING_NAME)


def estimate_tokens(text: str) -> int:
    return len(_get_encoding().encode(text))


def _chunk_type_hint(text: str, blocks: list[LayoutBlock]) -> str:
    if STAT_BLOCK_RE.search(text) or TABLE_RE.search(text):
        return "stat_block"
    if len(blocks) <= 3 and max((len(b.text) for b in blocks), default=0) < 80:
        return "table"
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


def _make_chunk(
    *,
    campaign_id: str,
    document_id: str,
    section_id: str | None,
    index: int,
    block_groups: list[tuple[LayoutPage, LayoutBlock]],
    needs_rechunk: bool = False,
) -> ChunkRecord:
    text = "\n\n".join(block.text for _, block in block_groups)
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

    blocks_only = [b for _, b in block_groups]
    return ChunkRecord(
        id=chunk_id(page_start, index),
        campaign_id=campaign_id,
        document_id=document_id,
        section_id=section_id,
        page_start=page_start,
        page_end=page_end,
        text=text,
        chunk_type_hint=_chunk_type_hint(text, blocks_only),
        token_count=estimate_tokens(text),
        source_spans=source_spans,
        needs_rechunk=needs_rechunk,
    )


def build_chunks(
    pages: list[LayoutPage],
    sections: list[SectionRecord],
    *,
    campaign_id: str,
    document_id: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[ChunkRecord]:
    if not pages:
        return []

    chunks: list[ChunkRecord] = []
    chunk_index = 0

    if len(sections) <= 1 and sections[0].title == "Document":
        block_items = _blocks_for_page_range(
            pages, sections[0].page_start, sections[0].page_end
        )
        for group in _split_blocks_into_chunks(block_items, max_tokens):
            chunks.append(
                _make_chunk(
                    campaign_id=campaign_id,
                    document_id=document_id,
                    section_id=sections[0].id,
                    index=chunk_index,
                    block_groups=group,
                    needs_rechunk=len(group) < 2,
                )
            )
            chunk_index += 1
        return chunks

    for section in sections:
        block_items = _blocks_for_page_range(
            pages, section.page_start, section.page_end
        )
        if not block_items:
            continue
        groups = _split_blocks_into_chunks(block_items, max_tokens)
        for group in groups:
            chunks.append(
                _make_chunk(
                    campaign_id=campaign_id,
                    document_id=document_id,
                    section_id=section.id,
                    index=chunk_index,
                    block_groups=group,
                    needs_rechunk=len(groups) == 1 and len(group) > 40,
                )
            )
            chunk_index += 1

    return chunks
