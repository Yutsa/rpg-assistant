from __future__ import annotations

from dataclasses import dataclass

from rpg_ingest.raw.block_merging import merge_drop_caps, merge_fragmented_blocks
from rpg_ingest.raw.chunking import build_chunks
from rpg_ingest.raw.extraction_config import ExtractorKind
from rpg_ingest.raw.filtering import filter_watermark_blocks
from rpg_ingest.raw.layout import LayoutPage, extract_layout_pages
from rpg_ingest.raw.pymupdf4llm_builder import (
    build_chunks_from_elements,
    build_sections_from_elements,
    refresh_element_kinds_from_layout,
)
from rpg_ingest.raw.pymupdf4llm_extractor import extract_document_pymupdf4llm
from rpg_ingest.raw.sections import detect_sections, refine_section_page_ends
from rpg_ingest.raw.stat_blocks import annotate_stat_blocks, resolve_profile
from rpg_ingest.raw.stat_blocks.types import StatBlockSpan
from rpg_core.models.raw import ChunkRecord, SectionRecord


@dataclass
class PipelineResult:
    pages: list[LayoutPage]
    sections: list[SectionRecord]
    chunks: list[ChunkRecord]
    stat_spans: list[StatBlockSpan]
    extractor: ExtractorKind


def run_raw_extraction_pipeline(
    pages: list[LayoutPage],
    *,
    campaign_id: str,
    document_id: str,
    game_system: str = "cof2",
    extractor: ExtractorKind = "legacy",
) -> PipelineResult:
    profile = resolve_profile(game_system, pages)
    filtered = filter_watermark_blocks(pages).pages
    merged = merge_fragmented_blocks(filtered, profile=profile).pages
    merged = merge_drop_caps(merged).pages
    stat_result = annotate_stat_blocks(merged, profile)
    layout_pages = stat_result.pages

    if extractor == "pymupdf4llm":
        raise ValueError(
            "Use run_raw_extraction_pipeline_pdf for pymupdf4llm extractor"
        )

    section_result = detect_sections(
        layout_pages,
        campaign_id=campaign_id,
        document_id=document_id,
        profile=profile,
    )
    sections = section_result.sections
    chunks = build_chunks(
        layout_pages,
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
        pages=layout_pages,
        sections=sections,
        chunks=chunks,
        stat_spans=stat_result.spans,
        extractor="legacy",
    )


def run_raw_extraction_pipeline_pdf(
    pdf_path,
    *,
    campaign_id: str,
    document_id: str,
    game_system: str = "cof2",
    extractor: ExtractorKind = "legacy",
) -> PipelineResult:
    import pymupdf

    document = pymupdf.open(pdf_path)
    try:
        if extractor == "pymupdf4llm":
            llm_extraction = extract_document_pymupdf4llm(document)
            layout_pages = llm_extraction.layout_pages
            elements = llm_extraction.elements
        else:
            layout_pages = extract_layout_pages(document)
            elements = None
    finally:
        document.close()

    profile = resolve_profile(game_system, layout_pages)
    filtered = filter_watermark_blocks(layout_pages).pages
    merged = merge_fragmented_blocks(filtered, profile=profile).pages
    merged = merge_drop_caps(merged).pages
    stat_result = annotate_stat_blocks(merged, profile)
    layout_pages = stat_result.pages

    if elements is not None:
        refresh_element_kinds_from_layout(elements, layout_pages)
        section_result = build_sections_from_elements(
            elements,
            campaign_id=campaign_id,
            document_id=document_id,
            page_count=len(layout_pages),
            profile=profile,
        )
        sections = section_result.sections
        chunks = build_chunks_from_elements(
            elements,
            section_result,
            layout_pages,
            campaign_id=campaign_id,
            document_id=document_id,
            stat_spans=stat_result.spans,
            profile=profile,
        )
    else:
        section_result = detect_sections(
            layout_pages,
            campaign_id=campaign_id,
            document_id=document_id,
            profile=profile,
        )
        sections = section_result.sections
        chunks = build_chunks(
            layout_pages,
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
        pages=layout_pages,
        sections=sections,
        chunks=chunks,
        stat_spans=stat_result.spans,
        extractor=extractor,
    )


def section_by_title(sections: list[SectionRecord], title: str) -> SectionRecord:
    for section in sections:
        if section.title == title:
            return section
    matches = [s for s in sections if title in s.title]
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
