from __future__ import annotations

from pathlib import Path

import pymupdf

from rpg_ingest.raw.extraction_config import normalize_extractor
from rpg_ingest.raw.pymupdf4llm_extractor import extract_document_pymupdf4llm
from rpg_ingest.raw.pymupdf4llm_builder import (
    _normalize_heading_levels,
    build_chunks_from_elements,
    build_sections_from_elements,
)
from rpg_ingest.raw.chunking import chunk_uniqueness_stats
from rpg_core.storage.ids import page_block_id
from tests.fixtures.pdf_synthetic import build_multicolumn_nested_headings_pdf
from tests.fixtures.pipeline import run_raw_extraction_pipeline_pdf


def test_normalize_extractor_aliases():
    assert normalize_extractor("legacy") == "legacy"
    assert normalize_extractor("pymupdf") == "legacy"
    assert normalize_extractor("pymupdf4llm") == "pymupdf4llm"
    assert normalize_extractor("layout") == "pymupdf4llm"


def test_pymupdf4llm_extractor_orders_multicolumn_headings(tmp_path: Path):
    pdf_path = tmp_path / "multicolumn.pdf"
    build_multicolumn_nested_headings_pdf(pdf_path)

    document = pymupdf.open(pdf_path)
    extraction = extract_document_pymupdf4llm(document)
    document.close()

    headings = [element for element in extraction.elements if element.kind == "heading"]
    assert [heading.text for heading in headings] == [
        "PARTIE I",
        "EN QUELQUES MOTS",
        "1.1 Sous-section",
        "PARTIE II",
    ]

    reading_order_text = [element.text for element in extraction.elements]
    partie_i = reading_order_text.index("PARTIE I")
    left_intro = reading_order_text.index("Résumé introductif dans la colonne gauche.")
    right_col = reading_order_text.index("Colonne droite indépendante.")
    sous_section = reading_order_text.index("1.1 Sous-section")
    assert partie_i < left_intro < sous_section
    assert partie_i < right_col < sous_section


def test_pymupdf4llm_heading_level_normalization(tmp_path: Path):
    pdf_path = tmp_path / "multicolumn.pdf"
    build_multicolumn_nested_headings_pdf(pdf_path)

    document = pymupdf.open(pdf_path)
    extraction = extract_document_pymupdf4llm(document)
    document.close()

    headings = [element for element in extraction.elements if element.kind == "heading"]
    _normalize_heading_levels(headings)
    assert [heading.level for heading in headings] == [1, 2, 2, 1]

    pdf_path = tmp_path / "multicolumn.pdf"
    build_multicolumn_nested_headings_pdf(pdf_path)

    result = run_raw_extraction_pipeline_pdf(
        pdf_path,
        campaign_id="camp_test",
        document_id="doc_test",
        extractor="pymupdf4llm",
    )

    titles = [section.title for section in result.sections]
    assert titles == ["PARTIE I", "EN QUELQUES MOTS", "1.1 Sous-section", "PARTIE II"]
    assert result.sections[1].parent_section_id == result.sections[0].id
    assert result.sections[2].parent_section_id == result.sections[0].id
    assert result.sections[3].parent_section_id is None

    chunk_texts = [chunk.text for chunk in result.chunks]
    assert any("Résumé introductif" in text for text in chunk_texts)
    assert any("Colonne droite indépendante" in text for text in chunk_texts)
    assert any("Corps de la sous-section" in text for text in chunk_texts)
    assert chunk_uniqueness_stats(result.chunks)["duplicate_chunk_count"] == 0


def test_pymupdf4llm_golden_matches_legacy_section_titles(tmp_path: Path):
    pdf_path = tmp_path / "multicolumn.pdf"
    build_multicolumn_nested_headings_pdf(pdf_path)

    legacy = run_raw_extraction_pipeline_pdf(
        pdf_path,
        campaign_id="camp_test",
        document_id="doc_legacy",
        extractor="legacy",
    )
    modern = run_raw_extraction_pipeline_pdf(
        pdf_path,
        campaign_id="camp_test",
        document_id="doc_llm",
        extractor="pymupdf4llm",
    )

    legacy_titles = {section.title for section in legacy.sections}
    modern_titles = {section.title for section in modern.sections}
    assert {
        "PARTIE I",
        "EN QUELQUES MOTS",
        "1.1 Sous-section",
        "PARTIE II",
    }.issubset(modern_titles)
    assert "PARTIE I" in legacy_titles
    assert "PARTIE II" in legacy_titles

    legacy_blocks = {
        page_block_id("doc_legacy", page.page_number, block.block_index)
        for page in legacy.pages
        for block in page.blocks
    }
    modern_blocks = {
        page_block_id("doc_llm", page.page_number, block.block_index)
        for page in modern.pages
        for block in page.blocks
    }
    assert len(legacy_blocks) > 0
    assert len(modern_blocks) > 0


def test_pymupdf4llm_chunks_cover_all_non_heading_blocks(tmp_path: Path):
    pdf_path = tmp_path / "multicolumn.pdf"
    build_multicolumn_nested_headings_pdf(pdf_path)

    document = pymupdf.open(pdf_path)
    extraction = extract_document_pymupdf4llm(document)
    document.close()

    section_result = build_sections_from_elements(
        extraction.elements,
        campaign_id="camp_test",
        document_id="doc_test",
        page_count=extraction.page_count,
    )
    chunks = build_chunks_from_elements(
        extraction.elements,
        section_result,
        extraction.layout_pages,
        campaign_id="camp_test",
        document_id="doc_test",
    )

    heading_positions = set(section_result.heading_anchors)
    referenced = {
        block_id
        for chunk in chunks
        for span in chunk.source_spans
        for block_id in span.page_block_ids
    }
    expected = {
        page_block_id("doc_test", element.page, element.block_index)
        for element in extraction.elements
        if element.kind != "heading"
    }
    assert referenced == expected
    assert not heading_positions.intersection(
        {
            (element.page, element.block_index)
            for element in extraction.elements
            if page_block_id("doc_test", element.page, element.block_index) in referenced
        }
    )
