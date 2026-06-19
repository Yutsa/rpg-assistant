"""Persist LLM-curated raw layer to the database."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rpg_ingest.raw.block_merging import merge_drop_caps, merge_fragmented_blocks
from rpg_ingest.raw.chunking import build_chunks, chunk_uniqueness_stats
from rpg_ingest.raw.coverage import document_coverage_ratio, page_text_coverage_ratio
from rpg_ingest.raw.filtering import filter_watermark_blocks
from rpg_ingest.raw.layout import LayoutPage
from rpg_ingest.raw.providers.legacy import LegacyExtractionProvider
from rpg_ingest.raw.sections import SectionDetectionResult, detect_sections, refine_section_page_ends
from rpg_ingest.raw.stat_blocks import annotate_stat_blocks, resolve_profile
from rpg_ingest.llm_curated.curation import curate_pipeline_result
from rpg_core.models.raw import (
    ChunkRecord,
    IngestionRunRecord,
    PageBlockRecord,
    PageRecord,
    SectionRecord,
)
from rpg_core.storage.db import get_connection
from rpg_core.storage.ids import document_id_from_hash, hash_file, new_id, page_block_id
from rpg_core.storage.repositories.raw import RawRepository

LLM_DOCUMENT_SUFFIX = "_llm_curated"


@dataclass
class LlmIngestResult:
    ingestion_run_id: str
    campaign_id: str
    document_id: str
    benchmark_id: str
    curation_notes: list[str]
    stats: dict[str, Any]


def _postprocess_pages(
    pages: list[LayoutPage],
    *,
    game_system: str,
) -> tuple[list[LayoutPage], object]:
    profile = resolve_profile(game_system, pages)
    pages = filter_watermark_blocks(pages).pages
    pages = merge_fragmented_blocks(pages, profile=profile).pages
    pages = merge_drop_caps(pages).pages
    stat_result = annotate_stat_blocks(pages, profile=profile)
    return stat_result.pages, stat_result


def _run_legacy_pipeline(
    pages: list[LayoutPage],
    stat_result: object,
    *,
    campaign_id: str,
    document_id: str,
    game_system: str,
) -> tuple[list[SectionRecord], list[ChunkRecord], list[tuple[int, int]]]:
    profile = resolve_profile(game_system, pages)
    section_result: SectionDetectionResult = detect_sections(
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
    refine_section_page_ends(section_result.sections, chunks)
    return section_result.sections, chunks, list(section_result.heading_anchors)


def ingest_llm_curated_pdf(
    pdf_path: Path,
    *,
    benchmark_id: str,
    campaign_id: str,
    game_system: str = "cof2",
    reimport: bool = True,
) -> LlmIngestResult:
    """Ingest a PDF with agent curation: legacy blocks + editorial section/chunk fixes."""
    content_hash = hash_file(pdf_path)
    base_document_id = document_id_from_hash(content_hash)
    document_id = f"{base_document_id}{LLM_DOCUMENT_SUFFIX}"
    run_id = new_id("run")

    extraction = LegacyExtractionProvider().extract(pdf_path)
    pages, stat_result = _postprocess_pages(extraction.pages, game_system=game_system)

    sections, chunks, heading_anchors = _run_legacy_pipeline(
        pages,
        stat_result,
        campaign_id=campaign_id,
        document_id=document_id,
        game_system=game_system,
    )

    curated = curate_pipeline_result(
        benchmark_id=benchmark_id,
        sections=sections,
        chunks=chunks,
    )
    sections = curated.sections
    chunks = curated.chunks
    refine_section_page_ends(sections, chunks)

    page_ratios = [
        page_text_coverage_ratio(p.text, p.width, p.height) for p in pages
    ]
    avg_coverage = document_coverage_ratio(page_ratios)

    with get_connection() as conn:
        repo = RawRepository(conn)
        repo.ensure_campaign(campaign_id, game_system=game_system)
        repo.upsert_document(
            document_id,
            campaign_id,
            pdf_path.name,
            len(pages),
            content_hash,
        )
        repo.create_ingestion_run(
            IngestionRunRecord(
                id=run_id,
                campaign_id=campaign_id,
                document_id=document_id,
                stage="raw",
                status="running",
            )
        )
        repo.update_ingestion_run(run_id, document_id=document_id)

        if reimport:
            repo.delete_document_raw_data(document_id)

        page_records: list[PageRecord] = []
        block_records: list[PageBlockRecord] = []
        for layout_page, ratio in zip(pages, page_ratios, strict=True):
            page_id = f"page_{document_id}_{layout_page.page_number:04d}"
            page_records.append(
                PageRecord(
                    id=page_id,
                    document_id=document_id,
                    page_number=layout_page.page_number,
                    text=layout_page.text,
                    extraction_method="llm_curated",
                    has_text=bool(layout_page.text.strip()),
                    text_coverage_ratio=ratio,
                    width=layout_page.width,
                    height=layout_page.height,
                )
            )
            for block in layout_page.blocks:
                block_records.append(
                    PageBlockRecord(
                        id=page_block_id(
                            document_id, layout_page.page_number, block.block_index
                        ),
                        document_id=document_id,
                        page_id=page_id,
                        page_number=layout_page.page_number,
                        block_index=block.block_index,
                        text=block.text,
                        bbox=block.bbox,
                        metadata=block.metadata,
                    )
                )

        repo.insert_pages(page_records)
        repo.insert_page_blocks(block_records)
        repo.insert_sections(sections)
        repo.insert_chunks(chunks)

        uniqueness = chunk_uniqueness_stats(chunks)
        stats = {
            "benchmark_id": benchmark_id,
            "extraction_method": "llm_curated",
            "curation_notes": curated.notes,
            "heading_anchors": heading_anchors,
            "page_count": len(pages),
            "block_count": sum(len(p.blocks) for p in pages),
            "section_count": len(sections),
            "chunk_count": len(chunks),
            "text_coverage_ratio": avg_coverage,
            "duplicate_chunk_count": uniqueness["duplicate_chunk_count"],
            "stat_block_count": len(stat_result.spans),
        }
        repo.update_ingestion_run(
            run_id,
            status="completed",
            stats=stats,
            finished=True,
        )

    return LlmIngestResult(
        ingestion_run_id=run_id,
        campaign_id=campaign_id,
        document_id=document_id,
        benchmark_id=benchmark_id,
        curation_notes=curated.notes,
        stats=stats,
    )
