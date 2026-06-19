"""Ensure Docling extraction beats legacy on benchmark fixtures."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from rpg_ingest.raw.layout import LayoutPage
from rpg_ingest.raw.providers.docling import DoclingExtractionProvider
from rpg_ingest.raw.providers.legacy import LegacyExtractionProvider
from tests.fixtures.docling_pdf import build_docling_synthetic_pdf
from tests.fixtures.provider_benchmark import (
    run_docling_pipeline,
    run_legacy_pipeline,
    score_page8_layout,
    score_synthetic_rpg,
)
from tests.test_page8_layout import _page8_fixture_pages


def _layout_pages_to_pdf(pages: list[LayoutPage], path: Path) -> None:
    doc = pymupdf.open()
    for layout_page in pages:
        page = doc.new_page(width=layout_page.width, height=layout_page.height)
        for block in sorted(layout_page.blocks, key=lambda item: item.bbox.y0):
            page.insert_text(
                (max(10.0, block.bbox.x0), max(20.0, block.bbox.y0)),
                block.text[:500],
                fontsize=block.metadata.get("max_font_size") or 11,
            )
    doc.save(str(path))
    doc.close()


@pytest.fixture(scope="module")
def synthetic_pdf(tmp_path_factory) -> Path:
    directory = tmp_path_factory.mktemp("provider_benchmark")
    return build_docling_synthetic_pdf(directory / "synthetic_rpg.pdf")


@pytest.fixture(scope="module")
def page8_pdf(tmp_path_factory) -> Path:
    directory = tmp_path_factory.mktemp("provider_benchmark")
    path = directory / "page8.pdf"
    _layout_pages_to_pdf(_page8_fixture_pages(), path)
    return path


def test_docling_beats_legacy_on_synthetic_rpg(synthetic_pdf: Path):
    legacy_ext = LegacyExtractionProvider().extract(synthetic_pdf)
    docling_ext = DoclingExtractionProvider().extract(synthetic_pdf)

    legacy_score, legacy_chunks, legacy_sections = run_legacy_pipeline(
        legacy_ext.pages,
        campaign_id="bench",
        document_id="doc_legacy",
    )
    docling_score, docling_chunks, docling_sections = run_docling_pipeline(
        docling_ext.pages,
        docling_ext.elements,
        campaign_id="bench",
        document_id="doc_docling",
    )

    legacy_ranked = score_synthetic_rpg(
        legacy_score, legacy_chunks, sections=legacy_sections
    )
    docling_ranked = score_synthetic_rpg(
        docling_score, docling_chunks, sections=docling_sections
    )

    assert docling_ranked.coverage_ok
    assert docling_ranked.beats(legacy_ranked), (
        f"docling={docling_ranked} legacy={legacy_ranked}"
    )


def test_docling_beats_legacy_on_page8_layout(page8_pdf: Path):
    legacy_ext = LegacyExtractionProvider().extract(page8_pdf)
    docling_ext = DoclingExtractionProvider().extract(page8_pdf)

    legacy_score, legacy_chunks, legacy_sections = run_legacy_pipeline(
        legacy_ext.pages,
        campaign_id="bench",
        document_id="doc_legacy_p8",
    )
    docling_score, docling_chunks, docling_sections = run_docling_pipeline(
        docling_ext.pages,
        docling_ext.elements,
        campaign_id="bench",
        document_id="doc_docling_p8",
    )

    legacy_ranked = score_page8_layout(
        legacy_score, legacy_chunks, sections=legacy_sections
    )
    docling_ranked = score_page8_layout(
        docling_score, docling_chunks, sections=docling_sections
    )

    assert docling_ranked.coverage_ok
    assert docling_ranked.beats(legacy_ranked), (
        f"docling={docling_ranked} legacy={legacy_ranked}"
    )
