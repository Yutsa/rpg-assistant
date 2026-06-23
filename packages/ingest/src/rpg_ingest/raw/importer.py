from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf

from rpg_ingest.raw.chunking import build_chunks, chunk_uniqueness_stats
from rpg_ingest.raw.stat_blocks import annotate_stat_blocks, resolve_profile
from rpg_ingest.raw.coverage import (
    DEFAULT_COVERAGE_THRESHOLD,
    document_coverage_ratio,
    is_scanned_or_unusable,
    page_text_coverage_ratio,
)
from rpg_ingest.raw.block_merging import merge_drop_caps, merge_fragmented_blocks
from rpg_ingest.raw.filtering import filter_watermark_blocks
from rpg_ingest.raw.extractor_compare_ingest import (
    attach_compare_lanes,
    build_extractor_compare_records,
    extract_compare_document_pages,
)
from rpg_ingest.raw.layout import RawLayoutPage, extract_raw_layout_pages
from rpg_ingest.raw.providers import DEFAULT_EXTRACTION_PROVIDER, resolve_extraction_provider
from rpg_ingest.raw.sections import detect_sections, refine_section_page_ends
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

INGEST_MODE_FULL = "full"
INGEST_MODE_LAYOUT_ONLY = "layout-only"
INGEST_MODE_EXTRACTOR_COMPARE = "extractor-compare"


@dataclass
class ImportResult:
    ingestion_run_id: str
    campaign_id: str
    document_id: str | None = None
    status: str = "pending"
    error_message: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)


def _load_raw_layout_pages(pdf_path: Path) -> list[RawLayoutPage]:
    document = pymupdf.open(pdf_path)
    try:
        return extract_raw_layout_pages(document)
    finally:
        document.close()


def _persist_extractor_compare(
    repo: RawRepository,
    *,
    run_id: str,
    campaign_id: str,
    document_id: str,
    pdf_path: Path,
    content_hash: str,
    pymupdf_pages: list[dict[str, Any]],
    pdfbox_pages: list[dict[str, Any]],
    avg_coverage: float,
    reimport: bool,
) -> ImportResult:
    repo.upsert_document(
        document_id,
        campaign_id,
        pdf_path.name,
        len(pdfbox_pages),
        content_hash,
    )
    repo.update_ingestion_run(run_id, document_id=document_id)

    if reimport:
        repo.delete_document_raw_data(document_id)

    pages, blocks = build_extractor_compare_records(
        document_id=document_id,
        pymupdf_pages=pymupdf_pages,
        pdfbox_pages=pdfbox_pages,
    )
    repo.insert_pages(pages)
    repo.insert_page_blocks(blocks)

    pymupdf_block_count = sum(
        len(page.get("blocks") or []) for page in pymupdf_pages
    )
    pdfbox_block_count = sum(len(page.get("blocks") or []) for page in pdfbox_pages)
    stats = {
        "source_pdf_path": str(pdf_path.resolve()),
        "page_count": len(pages),
        "block_count": len(blocks),
        "pymupdf_block_count": pymupdf_block_count,
        "pdfbox_block_count": pdfbox_block_count,
        "section_count": 0,
        "chunk_count": 0,
        "text_coverage_ratio": avg_coverage,
        "ingest_mode": INGEST_MODE_EXTRACTOR_COMPARE,
        "extraction_provider": "clojure",
        "extraction_method": "extractor_compare",
    }
    repo.update_ingestion_run(
        run_id,
        status="completed",
        document_id=document_id,
        stats=stats,
        finished=True,
    )
    return ImportResult(
        ingestion_run_id=run_id,
        campaign_id=campaign_id,
        document_id=document_id,
        status="completed",
        stats=stats,
    )


def _persist_layout_only(
    repo: RawRepository,
    *,
    run_id: str,
    campaign_id: str,
    document_id: str,
    pdf_path: Path,
    content_hash: str,
    raw_pages: list[RawLayoutPage],
    page_ratios: list[float],
    avg_coverage: float,
    reimport: bool,
) -> ImportResult:
    repo.upsert_document(
        document_id,
        campaign_id,
        pdf_path.name,
        len(raw_pages),
        content_hash,
    )
    repo.update_ingestion_run(run_id, document_id=document_id)

    if reimport:
        repo.delete_document_raw_data(document_id)

    pages: list[PageRecord] = []
    blocks: list[PageBlockRecord] = []
    for layout_page, ratio in zip(raw_pages, page_ratios, strict=True):
        page_id = f"page_{document_id}_{layout_page.page_number:04d}"
        pages.append(
            PageRecord(
                id=page_id,
                document_id=document_id,
                page_number=layout_page.page_number,
                text=layout_page.text,
                extraction_method="pymupdf_raw",
                has_text=bool(layout_page.text.strip()),
                text_coverage_ratio=ratio,
                width=layout_page.width,
                height=layout_page.height,
                raw_layout=layout_page.raw_layout,
            )
        )
        for block in layout_page.blocks:
            blocks.append(
                PageBlockRecord(
                    id=page_block_id(document_id, layout_page.page_number, block.block_index),
                    document_id=document_id,
                    page_id=page_id,
                    page_number=layout_page.page_number,
                    block_index=block.block_index,
                    text=block.text,
                    bbox=block.bbox,
                    metadata=block.metadata,
                )
            )

    repo.insert_pages(pages)
    repo.insert_page_blocks(blocks)

    stats = {
        "source_pdf_path": str(pdf_path.resolve()),
        "page_count": len(pages),
        "block_count": len(blocks),
        "section_count": 0,
        "chunk_count": 0,
        "text_coverage_ratio": avg_coverage,
        "ingest_mode": INGEST_MODE_LAYOUT_ONLY,
        "extraction_provider": DEFAULT_EXTRACTION_PROVIDER,
        "extraction_method": "pymupdf_raw",
    }
    repo.update_ingestion_run(
        run_id,
        status="completed",
        document_id=document_id,
        stats=stats,
        finished=True,
    )
    return ImportResult(
        ingestion_run_id=run_id,
        campaign_id=campaign_id,
        document_id=document_id,
        status="completed",
        stats=stats,
    )


def run(
    pdf_path: Path,
    *,
    campaign_id: str,
    campaign_title: str = "",
    game_system: str = "",
    coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD,
    reimport: bool = True,
    ingest_mode: str = INGEST_MODE_FULL,
    attach_compare_lanes_on_import: bool = True,
) -> ImportResult:
    """Stage A: deterministic raw extraction and persistence."""
    run_id = new_id("run")
    content_hash = hash_file(pdf_path)
    document_id = document_id_from_hash(content_hash)

    with get_connection() as conn:
        repo = RawRepository(conn)
        repo.ensure_campaign(campaign_id, title=campaign_title, game_system=game_system)
        repo.create_ingestion_run(
            IngestionRunRecord(
                id=run_id,
                campaign_id=campaign_id,
                stage="raw",
                status="running",
            )
        )

        if ingest_mode == INGEST_MODE_LAYOUT_ONLY:
            try:
                raw_pages = _load_raw_layout_pages(pdf_path)
            except Exception as exc:
                repo.update_ingestion_run(
                    run_id,
                    status="failed",
                    error_message=f"Could not extract PDF: {exc}",
                    finished=True,
                )
                return ImportResult(
                    ingestion_run_id=run_id,
                    campaign_id=campaign_id,
                    status="failed",
                    error_message=f"Could not extract PDF: {exc}",
                )
            page_ratios = [
                page_text_coverage_ratio(p.text, p.width, p.height) for p in raw_pages
            ]
            avg_coverage = document_coverage_ratio(page_ratios)
            if is_scanned_or_unusable(page_ratios, coverage_threshold):
                message = (
                    "PDF rejected: insufficient text coverage "
                    f"({avg_coverage:.2f} < {coverage_threshold}). "
                    "A text-based PDF is required; scanned/image-only PDFs are unsupported."
                )
                repo.update_ingestion_run(
                    run_id,
                    status="rejected",
                    error_message=message,
                    stats={"text_coverage_ratio": avg_coverage, "page_count": len(raw_pages)},
                    finished=True,
                )
                return ImportResult(
                    ingestion_run_id=run_id,
                    campaign_id=campaign_id,
                    document_id=document_id,
                    status="rejected",
                    error_message=message,
                    stats={"text_coverage_ratio": avg_coverage, "page_count": len(raw_pages)},
                )
            return _persist_layout_only(
                repo,
                run_id=run_id,
                campaign_id=campaign_id,
                document_id=document_id,
                pdf_path=pdf_path,
                content_hash=content_hash,
                raw_pages=raw_pages,
                page_ratios=page_ratios,
                avg_coverage=avg_coverage,
                reimport=reimport,
            )

        if ingest_mode == INGEST_MODE_EXTRACTOR_COMPARE:
            try:
                pymupdf_pages, pdfbox_pages = extract_compare_document_pages(pdf_path)
            except Exception as exc:
                repo.update_ingestion_run(
                    run_id,
                    status="failed",
                    error_message=f"Could not extract PDF for compare: {exc}",
                    finished=True,
                )
                return ImportResult(
                    ingestion_run_id=run_id,
                    campaign_id=campaign_id,
                    status="failed",
                    error_message=f"Could not extract PDF for compare: {exc}",
                )

            page_ratios = [
                page_text_coverage_ratio(
                    "\n\n".join(
                        str(block.get("text") or "")
                        for block in page.get("blocks") or []
                    ).strip(),
                    float(page["width"]),
                    float(page["height"]),
                )
                for page in pdfbox_pages
            ]
            avg_coverage = document_coverage_ratio(page_ratios)
            if is_scanned_or_unusable(page_ratios, coverage_threshold):
                message = (
                    "PDF rejected: insufficient text coverage "
                    f"({avg_coverage:.2f} < {coverage_threshold}). "
                    "A text-based PDF is required; scanned/image-only PDFs are unsupported."
                )
                repo.update_ingestion_run(
                    run_id,
                    status="rejected",
                    error_message=message,
                    stats={
                        "text_coverage_ratio": avg_coverage,
                        "page_count": len(pdfbox_pages),
                    },
                    finished=True,
                )
                return ImportResult(
                    ingestion_run_id=run_id,
                    campaign_id=campaign_id,
                    document_id=document_id,
                    status="rejected",
                    error_message=message,
                    stats={
                        "text_coverage_ratio": avg_coverage,
                        "page_count": len(pdfbox_pages),
                    },
                )

            return _persist_extractor_compare(
                repo,
                run_id=run_id,
                campaign_id=campaign_id,
                document_id=document_id,
                pdf_path=pdf_path,
                content_hash=content_hash,
                pymupdf_pages=pymupdf_pages,
                pdfbox_pages=pdfbox_pages,
                avg_coverage=avg_coverage,
                reimport=reimport,
            )

        try:
            provider = resolve_extraction_provider()
            extraction = provider.extract(pdf_path)
            layout_pages = extraction.pages
            extraction_method = extraction.extraction_method
            provider_metadata = extraction.metadata
        except Exception as exc:
            repo.update_ingestion_run(
                run_id,
                status="failed",
                error_message=f"Could not extract PDF: {exc}",
                finished=True,
            )
            return ImportResult(
                ingestion_run_id=run_id,
                campaign_id=campaign_id,
                status="failed",
                error_message=f"Could not extract PDF: {exc}",
            )

        stat_profile = resolve_profile(game_system, layout_pages)
        filter_result = filter_watermark_blocks(layout_pages)
        layout_pages = filter_result.pages
        merge_result = merge_fragmented_blocks(layout_pages, profile=stat_profile)
        layout_pages = merge_result.pages
        drop_cap_result = merge_drop_caps(layout_pages)
        layout_pages = drop_cap_result.pages
        stat_result = annotate_stat_blocks(layout_pages, stat_profile)
        layout_pages = stat_result.pages
        page_ratios = [
            page_text_coverage_ratio(p.text, p.width, p.height) for p in layout_pages
        ]
        avg_coverage = document_coverage_ratio(page_ratios)

        if is_scanned_or_unusable(page_ratios, coverage_threshold):
            message = (
                "PDF rejected: insufficient text coverage "
                f"({avg_coverage:.2f} < {coverage_threshold}). "
                "A text-based PDF is required; scanned/image-only PDFs are unsupported."
            )
            repo.update_ingestion_run(
                run_id,
                status="rejected",
                error_message=message,
                stats={"text_coverage_ratio": avg_coverage, "page_count": len(layout_pages)},
                finished=True,
            )
            return ImportResult(
                ingestion_run_id=run_id,
                campaign_id=campaign_id,
                document_id=document_id,
                status="rejected",
                error_message=message,
                stats={"text_coverage_ratio": avg_coverage, "page_count": len(layout_pages)},
            )

        repo.upsert_document(
            document_id,
            campaign_id,
            pdf_path.name,
            len(layout_pages),
            content_hash,
        )
        repo.update_ingestion_run(run_id, document_id=document_id)

        if reimport:
            repo.delete_document_raw_data(document_id)

        pages: list[PageRecord] = []
        blocks: list[PageBlockRecord] = []
        for layout_page, ratio in zip(layout_pages, page_ratios, strict=True):
            page_id = f"page_{document_id}_{layout_page.page_number:04d}"
            pages.append(
                PageRecord(
                    id=page_id,
                    document_id=document_id,
                    page_number=layout_page.page_number,
                    text=layout_page.text,
                    extraction_method=extraction_method,
                    has_text=bool(layout_page.text.strip()),
                    text_coverage_ratio=ratio,
                    width=layout_page.width,
                    height=layout_page.height,
                )
            )
            for block in layout_page.blocks:
                blocks.append(
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

        section_result = detect_sections(
            layout_pages,
            campaign_id=campaign_id,
            document_id=document_id,
            profile=stat_profile,
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
            profile=stat_profile,
        )
        refine_section_page_ends(sections, chunks)

        repo.insert_pages(pages)
        repo.insert_page_blocks(blocks)
        repo.insert_sections(sections)
        repo.insert_chunks(chunks)

        uniqueness = chunk_uniqueness_stats(chunks)
        stats: dict[str, Any] = {
            "source_pdf_path": str(pdf_path.resolve()),
            "page_count": len(pages),
            "block_count": len(blocks),
            "section_count": len(sections),
            "chunk_count": len(chunks),
            "text_coverage_ratio": avg_coverage,
            "needs_rechunk_count": sum(1 for c in chunks if c.needs_rechunk),
            "watermark_blocks_removed": filter_result.removed_block_count,
            "merged_block_count": merge_result.merged_block_count,
            "drop_cap_merged_count": drop_cap_result.merged_block_count,
            "stat_block_count": len(stat_result.spans),
            "stat_block_profile": stat_result.profile_id,
            "singleton_heading_count": sum(
                1 for section in sections if len(section.title.strip()) == 1
            ),
            "extraction_provider": DEFAULT_EXTRACTION_PROVIDER,
            "extraction_method": extraction_method,
            "ingest_mode": INGEST_MODE_FULL,
            **uniqueness,
            **provider_metadata,
        }
        if attach_compare_lanes_on_import:
            try:
                stats.update(
                    attach_compare_lanes(
                        repo,
                        document_id=document_id,
                        pdf_path=pdf_path,
                    )
                )
            except Exception as exc:
                stats["compare_lanes_error"] = str(exc)
        repo.update_ingestion_run(
            run_id,
            status="completed",
            document_id=document_id,
            stats=stats,
            finished=True,
        )

        return ImportResult(
            ingestion_run_id=run_id,
            campaign_id=campaign_id,
            document_id=document_id,
            status="completed",
            stats=stats,
        )
