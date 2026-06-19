from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixtures.extractor_scoring import (
    score_momie_synopsis,
    score_multicolumn,
    score_page8_layout,
)
from tests.fixtures.pdf_from_layout import build_momie_synopsis_pdf, build_page8_layout_pdf
from tests.fixtures.pdf_synthetic import build_multicolumn_nested_headings_pdf
from tests.fixtures.pipeline import run_raw_extraction_pipeline_pdf


@pytest.mark.parametrize(
    ("builder", "scorer"),
    [
        (build_multicolumn_nested_headings_pdf, score_multicolumn),
        (build_page8_layout_pdf, score_page8_layout),
        (build_momie_synopsis_pdf, score_momie_synopsis),
    ],
    ids=["multicolumn", "page8", "momie_synopsis"],
)
def test_pymupdf4llm_beats_legacy_on_benchmarks(
    tmp_path: Path,
    builder,
    scorer,
):
    pdf_path = tmp_path / "benchmark.pdf"
    builder(pdf_path)

    legacy = run_raw_extraction_pipeline_pdf(
        pdf_path,
        campaign_id="bench",
        document_id="legacy",
        extractor="legacy",
    )
    modern = run_raw_extraction_pipeline_pdf(
        pdf_path,
        campaign_id="bench",
        document_id="modern",
        extractor="pymupdf4llm",
    )

    legacy_score = scorer(legacy)
    modern_score = scorer(modern)
    assert modern_score >= legacy_score, (
        f"pymupdf4llm score {modern_score} < legacy {legacy_score}\n"
        f"legacy sections: {[s.title for s in legacy.sections]}\n"
        f"modern sections: {[s.title for s in modern.sections]}"
    )
    assert modern_score > 0
