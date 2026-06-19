"""Integration tests for the Docling raw extraction pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpg_ingest.raw.block_merging import merge_drop_caps, merge_fragmented_blocks
from rpg_ingest.raw.chunking import chunk_uniqueness_stats
from rpg_ingest.raw.docling_chunking import build_chunks_from_elements
from rpg_ingest.raw.docling_sections import detect_sections_from_elements
from rpg_ingest.raw.filtering import filter_watermark_blocks
from rpg_ingest.raw.providers.docling import DoclingExtractionProvider
from rpg_ingest.raw.stat_blocks import annotate_stat_blocks, resolve_profile
from rpg_ingest.raw.sections import refine_section_page_ends
from rpg_core.storage.ids import page_block_id
from tests.fixtures.docling_pdf import build_docling_synthetic_pdf


@pytest.fixture(scope="module")
def synthetic_pdf(tmp_path_factory) -> Path:
    pdf_dir = tmp_path_factory.mktemp("docling_pdfs")
    return build_docling_synthetic_pdf(pdf_dir / "synthetic_rpg.pdf")


@pytest.fixture(scope="module")
def docling_extraction(synthetic_pdf: Path):
    provider = DoclingExtractionProvider()
    return provider.extract(synthetic_pdf)


def test_docling_extracts_elements_and_pages(docling_extraction):
    assert docling_extraction.provider_id == "docling"
    assert len(docling_extraction.pages) >= 1
    assert len(docling_extraction.elements) >= 3
    all_text = " ".join(element.text for element in docling_extraction.elements)
    assert "CHRONIQUES" in all_text.upper() or "CRYPT" in all_text.upper()


def test_docling_pipeline_covers_blocks_without_duplicates(docling_extraction):
    pages = docling_extraction.pages
    elements = docling_extraction.elements
    profile = resolve_profile("cof2", pages)
    pages = filter_watermark_blocks(pages).pages
    pages = merge_fragmented_blocks(pages, profile=profile).pages
    pages = merge_drop_caps(pages).pages
    stat_result = annotate_stat_blocks(pages, profile)
    pages = stat_result.pages

    section_result = detect_sections_from_elements(
        elements,
        pages,
        campaign_id="camp_docling",
        document_id="doc_docling_test",
        profile=profile,
    )
    chunks = build_chunks_from_elements(
        elements,
        pages,
        section_result.sections,
        campaign_id="camp_docling",
        document_id="doc_docling_test",
        heading_anchors=section_result.heading_anchors,
        stat_spans=stat_result.spans,
        profile=profile,
    )
    refine_section_page_ends(section_result.sections, chunks)

    heading_positions = set(section_result.heading_anchors)
    referenced = {
        block_id
        for chunk in chunks
        for span in chunk.source_spans
        for block_id in span.page_block_ids
    }
    content_block_ids = {
        page_block_id("doc_docling_test", page.page_number, block.block_index)
        for page in pages
        for block in page.blocks
        if (page.page_number, block.block_index) not in heading_positions
    }
    assert content_block_ids.issubset(referenced)
    assert referenced == content_block_ids

    uniqueness = chunk_uniqueness_stats(chunks)
    assert uniqueness["duplicate_chunk_count"] == 0
    assert uniqueness["chunk_unique_block_signature_ratio"] == 1.0


def test_docling_pipeline_detects_sections(docling_extraction):
    pages = docling_extraction.pages
    elements = docling_extraction.elements
    profile = resolve_profile("cof2", pages)
    section_result = detect_sections_from_elements(
        elements,
        pages,
        campaign_id="camp_docling",
        document_id="doc_docling_test",
        profile=profile,
    )
    titles = [section.title.upper() for section in section_result.sections]
    assert any("CHRON" in title or "CRYPT" in title for title in titles)


def test_docling_pipeline_detects_stat_block(docling_extraction):
    pages = docling_extraction.pages
    profile = resolve_profile("cof2", pages)
    stat_result = annotate_stat_blocks(pages, profile)
    assert len(stat_result.spans) >= 1
    names = [span.blocks[0].text for span in stat_result.spans if span.blocks]
    joined = " ".join(names).upper()
    assert "MOMIE" in joined
