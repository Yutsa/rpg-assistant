from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf

from rpg_assistant.ingestion.raw.chunking import build_chunks
from rpg_assistant.ingestion.raw.coverage import (
    DEFAULT_COVERAGE_THRESHOLD,
    document_coverage_ratio,
    is_scanned_or_unusable,
    page_text_coverage_ratio,
)
from rpg_assistant.ingestion.raw.block_merging import merge_fragmented_blocks
from rpg_assistant.ingestion.raw.filtering import filter_watermark_blocks
from rpg_assistant.ingestion.raw.layout import extract_layout_pages
from rpg_assistant.ingestion.raw.sections import detect_sections
from rpg_assistant.models.raw import (
    ChunkRecord,
    IngestionRunRecord,
    PageBlockRecord,
    PageRecord,
    SectionRecord,
)
from rpg_assistant.storage.db import get_connection
from rpg_assistant.storage.ids import document_id_from_hash, hash_file, new_id, page_block_id
from rpg_assistant.storage.repositories.raw import RawRepository


@dataclass
class ImportResult:
    ingestion_run_id: str
    campaign_id: str
    document_id: str | None = None
    status: str = "pending"
    error_message: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)


def run(
    pdf_path: Path,
    *,
    campaign_id: str,
    campaign_title: str = "",
    game_system: str = "",
    coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD,
    reimport: bool = True,
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

        try:
            document = pymupdf.open(pdf_path)
        except Exception as exc:
            repo.update_ingestion_run(
                run_id,
                status="failed",
                error_message=f"Could not open PDF: {exc}",
                finished=True,
            )
            return ImportResult(
                ingestion_run_id=run_id,
                campaign_id=campaign_id,
                status="failed",
                error_message=f"Could not open PDF: {exc}",
            )

        layout_pages = extract_layout_pages(document)
        filter_result = filter_watermark_blocks(layout_pages)
        layout_pages = filter_result.pages
        merge_result = merge_fragmented_blocks(layout_pages)
        layout_pages = merge_result.pages
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
        for layout_page in layout_pages:
            page_id = f"page_{document_id}_{layout_page.page_number:04d}"
            ratio = page_text_coverage_ratio(
                layout_page.text, layout_page.width, layout_page.height
            )
            pages.append(
                PageRecord(
                    id=page_id,
                    document_id=document_id,
                    page_number=layout_page.page_number,
                    text=layout_page.text,
                    has_text=bool(layout_page.text.strip()),
                    text_coverage_ratio=ratio,
                    width=layout_page.width,
                    height=layout_page.height,
                )
            )
            for block in layout_page.blocks:
                blocks.append(
                    PageBlockRecord(
                        id=page_block_id(layout_page.page_number, block.block_index),
                        document_id=document_id,
                        page_id=page_id,
                        page_number=layout_page.page_number,
                        block_index=block.block_index,
                        text=block.text,
                        bbox=block.bbox,
                        metadata=block.metadata,
                    )
                )

        sections: list[SectionRecord] = detect_sections(
            layout_pages, campaign_id=campaign_id, document_id=document_id
        )
        chunks: list[ChunkRecord] = build_chunks(
            layout_pages, sections, campaign_id=campaign_id, document_id=document_id
        )

        repo.insert_pages(pages)
        repo.insert_page_blocks(blocks)
        repo.insert_sections(sections)
        repo.insert_chunks(chunks)

        stats = {
            "page_count": len(pages),
            "block_count": len(blocks),
            "section_count": len(sections),
            "chunk_count": len(chunks),
            "text_coverage_ratio": avg_coverage,
            "needs_rechunk_count": sum(1 for c in chunks if c.needs_rechunk),
            "watermark_blocks_removed": filter_result.removed_block_count,
            "merged_block_count": merge_result.merged_block_count,
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
