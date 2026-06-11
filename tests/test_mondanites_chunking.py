from pathlib import Path

import pymupdf
import pytest

from rpg_assistant.ingestion.raw.block_merging import merge_drop_caps, merge_fragmented_blocks
from rpg_assistant.ingestion.raw.chunking import build_chunks, chunk_uniqueness_stats
from rpg_assistant.ingestion.raw.filtering import filter_watermark_blocks
from rpg_assistant.ingestion.raw.layout import extract_layout_pages
from rpg_assistant.ingestion.raw.sections import detect_sections
from rpg_assistant.ingestion.raw.stat_blocks import annotate_stat_blocks, resolve_profile
from rpg_assistant.storage.ids import page_block_id

MONDANITES_PDF = Path(
    "/home/edouard/Téléchargements/COF2_10_Mondanites_Et_Momies_web_v1a.pdf"
)


def _referenced_block_ids(chunks) -> set[str]:
    return {
        block_id
        for chunk in chunks
        for span in chunk.source_spans
        for block_id in span.page_block_ids
    }


@pytest.mark.skipif(not MONDANITES_PDF.exists(), reason="Mondanités PDF not available locally")
def test_mondanites_chunk_quality():
    document = pymupdf.open(MONDANITES_PDF)
    pages = extract_layout_pages(document)
    profile = resolve_profile("cof2", pages)
    pages = filter_watermark_blocks(pages).pages
    pages = merge_fragmented_blocks(pages, profile=profile).pages
    pages = merge_drop_caps(pages).pages
    stat_result = annotate_stat_blocks(pages, profile)
    pages = stat_result.pages

    section_result = detect_sections(
        pages, campaign_id="momie", document_id="doc_mondanites", profile=profile
    )
    chunks = build_chunks(
        pages,
        section_result.sections,
        campaign_id="momie",
        document_id="doc_mondanites",
        heading_anchors=section_result.heading_anchors,
        stat_spans=stat_result.spans,
        profile=profile,
    )

    uniqueness = chunk_uniqueness_stats(chunks)
    heading_positions = set(section_result.heading_anchors)
    content_block_ids = {
        page_block_id(page.page_number, block.block_index)
        for page in pages
        for block in page.blocks
        if (page.page_number, block.block_index) not in heading_positions
    }
    referenced = _referenced_block_ids(chunks)

    assert len(chunks) <= 80
    assert uniqueness["chunk_unique_block_signature_ratio"] >= 0.98
    assert uniqueness["duplicate_chunk_count"] <= 1
    assert referenced == content_block_ids
    assert all(len(section.title.strip()) != 1 for section in section_result.sections)
    section_titles = [section.title for section in section_result.sections]
    assert not any("AZULRIA" in title for title in section_titles)
    assert not any("TALESS RHANN" in title for title in section_titles)

    page_15_stat_chunks = [
        chunk
        for chunk in chunks
        if chunk.page_start <= 15 <= chunk.page_end and chunk.chunk_type_hint == "stat_block"
    ]
    assert page_15_stat_chunks
    assert any(chunk.metadata.get("stat_block", {}).get("name") for chunk in page_15_stat_chunks)

    page_five_chunks = [chunk for chunk in chunks if chunk.page_start == 5 and chunk.page_end == 5]
    page_five_signatures = {
        frozenset(
            block_id for span in chunk.source_spans for block_id in span.page_block_ids
        )
        for chunk in page_five_chunks
    }
    assert len(page_five_chunks) <= 5
    assert len(page_five_signatures) == len(page_five_chunks)
