from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from rpg_ingest.raw.pymupdf4llm_extractor import (
    _classify_box,
    _markdown_heading_level,
    extract_document_pymupdf4llm,
)
from tests.fixtures.pdf_from_layout import build_momie_synopsis_pdf


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

    kind, level = _classify_box(
        "table",
        "|A|B|",
        markdown_text="",
        markdown_pos=None,
    )
    assert kind == "table"
    assert level is None


def test_classify_box_stat_block_candidate():
    kind, _ = _classify_box(
        "text",
        "Momie | NC 12",
        markdown_text="",
        markdown_pos=None,
    )
    assert kind == "stat_block_candidate"


def test_reconcile_restores_missing_synopsis_paragraph(tmp_path: Path):
    pdf_path = tmp_path / "momie.pdf"
    build_momie_synopsis_pdf(pdf_path)

    document = pymupdf.open(pdf_path)
    extraction = extract_document_pymupdf4llm(document)
    document.close()

    page_two = next(page for page in extraction.layout_pages if page.page_number == 2)
    texts = [block.text for block in page_two.blocks]
    assert any("MALÉDICTION" in text for text in texts)
    assert any("malédiction pèse sur la région" in text for text in texts)
