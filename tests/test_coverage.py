from rpg_assistant.ingestion.raw.coverage import (
    DEFAULT_COVERAGE_THRESHOLD,
    document_coverage_ratio,
    is_scanned_or_unusable,
    page_text_coverage_ratio,
)


def test_page_text_coverage_empty_page():
    assert page_text_coverage_ratio("", 612, 792) == 0.0


def test_page_text_coverage_nonzero():
    text = "word " * 200
    ratio = page_text_coverage_ratio(text, 612, 792)
    assert 0 < ratio <= 1.0


def test_document_coverage_average():
    assert document_coverage_ratio([0.2, 0.4, 0.6]) == 0.4


def test_scanned_pdf_rejected():
    assert is_scanned_or_unusable([0.01, 0.02], DEFAULT_COVERAGE_THRESHOLD)


def test_text_pdf_accepted():
    assert not is_scanned_or_unusable([0.5, 0.6, 0.7], DEFAULT_COVERAGE_THRESHOLD)
