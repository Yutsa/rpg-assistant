"""Shared raw extraction pipeline for ingestion tests (no database)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rpg_ingest.raw.block_merging import BlockMergeResult, merge_drop_caps, merge_fragmented_blocks
from rpg_ingest.raw.chunking import build_chunks
from rpg_ingest.raw.docling_chunking import build_chunks_from_elements as build_docling_chunks
from rpg_ingest.raw.docling_sections import detect_sections_from_elements as detect_docling_sections
from rpg_ingest.raw.filtering import filter_watermark_blocks
from rpg_ingest.raw.layout import LayoutPage, extract_layout_pages
from rpg_ingest.raw.pymupdf4llm_builder import (
    build_chunks_from_elements as build_pymupdf4llm_chunks,
    build_sections_from_elements as detect_pymupdf4llm_sections,
    refresh_element_kinds_from_layout,
)
from rpg_ingest.raw.providers import resolve_extraction_provider
from rpg_ingest.raw.sections import detect_sections, refine_section_page_ends
from rpg_ingest.raw.stat_blocks import annotate_stat_blocks, resolve_profile
from rpg_ingest.raw.stat_blocks.types import StatBlockSpan
from rpg_core.models.raw import ChunkRecord, SectionRecord

ProviderName = str


@dataclass
class PipelineResult:
    pages: list[LayoutPage]
    sections: list[SectionRecord]
    chunks: list[ChunkRecord]
    stat_spans: list[StatBlockSpan]
    provider: ProviderName


def _postprocess_pages(
    pages: list[LayoutPage],
    *,
    game_system: str,
    provider: ProviderName,
) -> tuple[list[LayoutPage], object]:
    profile = resolve_profile(game_system, pages)
    pages = filter_watermark_blocks(pages).pages
    if provider == "pymupdf4llm":
        merged = pages
    else:
        merged = merge_fragmented_blocks(pages, profile=profile).pages
    merged = merge_drop_caps(merged).pages
    stat_result = annotate_stat_blocks(merged, profile)
    return stat_result.pages, stat_result


def run_raw_extraction_pipeline(
    pages: list[LayoutPage],
    *,
    campaign_id: str,
    document_id: str,
    game_system: str = "cof2",
    provider: ProviderName = "legacy",
) -> PipelineResult:
    pages, stat_result = _postprocess_pages(pages, game_system=game_system, provider=provider)
    profile = resolve_profile(game_system, pages)

    section_result = detect_sections(
        pages,
        campaign_id=campaign_id,
        document_id=document_id,
        profile=profile,
    )
    sections = section_result.sections
    chunks = build_chunks(
        pages,
        sections,
        campaign_id=campaign_id,
        document_id=document_id,
        heading_anchors=section_result.heading_anchors,
        content_only_section_ids=section_result.content_only_section_ids,
        stat_spans=stat_result.spans,
        profile=profile,
    )
    refine_section_page_ends(sections, chunks)
    return PipelineResult(
        pages=pages,
        sections=sections,
        chunks=chunks,
        stat_spans=stat_result.spans,
        provider="legacy",
    )


def run_raw_extraction_pipeline_pdf(
    pdf_path: Path,
    *,
    campaign_id: str,
    document_id: str,
    game_system: str = "cof2",
    provider: ProviderName = "legacy",
) -> PipelineResult:
    extraction = resolve_extraction_provider(provider).extract(pdf_path)
    layout_pages = extraction.pages
    elements = extraction.elements

    pages, stat_result = _postprocess_pages(
        layout_pages,
        game_system=game_system,
        provider=provider,
    )
    profile = resolve_profile(game_system, pages)

    if elements and provider == "pymupdf4llm":
        refresh_element_kinds_from_layout(elements, pages)
        section_result = detect_pymupdf4llm_sections(
            elements,
            pages,
            campaign_id=campaign_id,
            document_id=document_id,
            profile=profile,
        )
        chunks = build_pymupdf4llm_chunks(
            elements,
            pages,
            section_result.sections,
            campaign_id=campaign_id,
            document_id=document_id,
            heading_anchors=section_result.heading_anchors,
            content_only_section_ids=section_result.content_only_section_ids,
            stat_spans=stat_result.spans,
            profile=profile,
        )
    elif elements:
        section_result = detect_docling_sections(
            elements,
            pages,
            campaign_id=campaign_id,
            document_id=document_id,
            profile=profile,
        )
        chunks = build_docling_chunks(
            elements,
            pages,
            section_result.sections,
            campaign_id=campaign_id,
            document_id=document_id,
            heading_anchors=section_result.heading_anchors,
            stat_spans=stat_result.spans,
            profile=profile,
        )
    else:
        section_result = detect_sections(
            pages,
            campaign_id=campaign_id,
            document_id=document_id,
            profile=profile,
        )
        chunks = build_chunks(
            pages,
            section_result.sections,
            campaign_id=campaign_id,
            document_id=document_id,
            heading_anchors=section_result.heading_anchors,
            content_only_section_ids=section_result.content_only_section_ids,
            stat_spans=stat_result.spans,
            profile=profile,
        )

    sections = section_result.sections
    refine_section_page_ends(sections, chunks)
    return PipelineResult(
        pages=pages,
        sections=sections,
        chunks=chunks,
        stat_spans=stat_result.spans,
        provider=provider,
    )


def section_by_title(sections: list[SectionRecord], title: str) -> SectionRecord:
    needle = title.casefold()
    for section in sections:
        if section.title.casefold() == needle:
            return section
    matches = [s for s in sections if needle in s.title.casefold()]
    if len(matches) == 1:
        return matches[0]
    raise AssertionError(f"Section not found for title={title!r}; got {[s.title for s in sections]}")


def chunk_texts_for_section(
    chunks: list[ChunkRecord],
    sections: list[SectionRecord],
    title_substr: str,
) -> list[str]:
    section = section_by_title(sections, title_substr)
    return [chunk.text for chunk in chunks if chunk.section_id == section.id]


def stat_block_ability_titles(chunks: list[ChunkRecord], name: str) -> list[str]:
    name_key = name.casefold()
    for chunk in chunks:
        stat_block = chunk.metadata.get("stat_block") or {}
        chunk_name = (stat_block.get("name") or "").casefold()
        if chunk_name == name_key or name_key in chunk_name:
            return [ability["title"] for ability in stat_block.get("abilities", [])]
    raise AssertionError(f"No stat_block chunk found for name={name!r}")


def contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)
