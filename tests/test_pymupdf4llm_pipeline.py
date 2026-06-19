from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from rpg_ingest.raw.pymupdf4llm_extractor import (
    _classify_box,
    _markdown_heading_level,
    extract_document_pymupdf4llm,
)
from rpg_ingest.raw.pymupdf4llm_builder import (
    _normalize_heading_levels,
    build_chunks_from_elements,
    build_sections_from_elements,
)
from rpg_ingest.raw.chunking import chunk_uniqueness_stats
from rpg_ingest.raw.providers import resolve_extraction_provider
from rpg_ingest.raw.providers.legacy import LegacyExtractionProvider
from rpg_ingest.raw.providers.pymupdf4llm import Pymupdf4LlmExtractionProvider
from rpg_core.storage.ids import page_block_id
from tests.fixtures.pdf_from_layout import build_momie_synopsis_pdf
from tests.fixtures.pdf_synthetic import build_multicolumn_nested_headings_pdf
from tests.fixtures.pipeline import run_raw_extraction_pipeline_pdf


@pytest.mark.parametrize(
    ("markdown", "pos", "expected"),
    [
        ("## Chapter 1\n\nBody", 0, 2),
        ("# Title\n\n## Sub", 10, 2),
        ("Plain text", 0, 1),
    ],
)
def test_markdown_heading_level(markdown: str, pos: int, expected: int):
    assert _markdown_heading_level(markdown, pos) == expected


def test_classify_box_heading_and_table():
    kind, level = _classify_box(
        "section-header",
        "Chapter 1",
        markdown_text="## Chapter 1\n\nBody",
        markdown_pos=(0, 13),
    )
    assert kind == "heading"
    assert level == 2


def test_resolve_pymupdf4llm_provider() -> None:
    provider = resolve_extraction_provider("pymupdf4llm")
    assert isinstance(provider, Pymupdf4LlmExtractionProvider)


def test_reconcile_restores_missing_synopsis_paragraph(tmp_path: Path):
    pdf_path = tmp_path / "momie.pdf"
    build_momie_synopsis_pdf(pdf_path)

    extraction = Pymupdf4LlmExtractionProvider().extract(pdf_path)
    page_two = next(page for page in extraction.pages if page.page_number == 2)
    texts = [block.text for block in page_two.blocks]
    assert any("MALÉDICTION" in text for text in texts)
    assert any("malédiction pèse sur la région" in text for text in texts)


def test_pymupdf4llm_extractor_orders_multicolumn_headings(tmp_path: Path):
    pdf_path = tmp_path / "multicolumn.pdf"
    build_multicolumn_nested_headings_pdf(pdf_path)

    extraction = Pymupdf4LlmExtractionProvider().extract(pdf_path)
    headings = [element for element in extraction.elements if element.is_heading]
    assert [heading.text for heading in headings] == [
        "PARTIE I",
        "EN QUELQUES MOTS",
        "1.1 Sous-section",
        "PARTIE II",
    ]


def test_pymupdf4llm_heading_level_normalization(tmp_path: Path):
    pdf_path = tmp_path / "multicolumn.pdf"
    build_multicolumn_nested_headings_pdf(pdf_path)
    extraction = Pymupdf4LlmExtractionProvider().extract(pdf_path)
    headings = [element for element in extraction.elements if element.is_heading]
    _normalize_heading_levels(headings)
    assert [heading.heading_level for heading in headings] == [1, 2, 2, 1]


def test_pymupdf4llm_builder_nested_sections_and_chunks(tmp_path: Path):
    pdf_path = tmp_path / "multicolumn.pdf"
    build_multicolumn_nested_headings_pdf(pdf_path)

    result = run_raw_extraction_pipeline_pdf(
        pdf_path,
        campaign_id="camp_test",
        document_id="doc_test",
        provider="pymupdf4llm",
    )

    titles = [section.title for section in result.sections]
    assert titles == ["PARTIE I", "EN QUELQUES MOTS", "1.1 Sous-section", "PARTIE II"]
    assert chunk_uniqueness_stats(result.chunks)["duplicate_chunk_count"] == 0


def test_pymupdf4llm_matches_legacy_on_multicolumn_benchmark(tmp_path: Path):
    pdf_path = tmp_path / "multicolumn.pdf"
    build_multicolumn_nested_headings_pdf(pdf_path)

    legacy = run_raw_extraction_pipeline_pdf(
        pdf_path, campaign_id="c", document_id="leg", provider="legacy"
    )
    modern = run_raw_extraction_pipeline_pdf(
        pdf_path, campaign_id="c", document_id="llm", provider="pymupdf4llm"
    )

    legacy_partie = next(
        s for s in legacy.sections if s.title == "PARTIE I"
    )
    modern_partie = next(
        s for s in modern.sections if s.title == "PARTIE I"
    )
    legacy_text = " ".join(
        c.text for c in legacy.chunks if c.section_id == legacy_partie.id
    )
    modern_text = " ".join(
        c.text for c in modern.chunks if c.section_id == modern_partie.id
    )
    assert legacy_text == modern_text
