from __future__ import annotations

DEFAULT_COVERAGE_THRESHOLD = 0.3


def page_text_coverage_ratio(text: str, page_width: float, page_height: float) -> float:
    """Estimate how much of a page area is covered by extracted text."""
    if page_width <= 0 or page_height <= 0:
        return 0.0
    stripped = text.strip()
    if not stripped:
        return 0.0
    char_count = len(stripped)
    page_area = page_width * page_height
    # Heuristic: ~1 char per 50 square points of readable area at typical book density.
    estimated_text_area = char_count * 50.0
    return min(1.0, estimated_text_area / page_area)


def document_coverage_ratio(page_ratios: list[float]) -> float:
    if not page_ratios:
        return 0.0
    return sum(page_ratios) / len(page_ratios)


def is_scanned_or_unusable(
    page_ratios: list[float],
    threshold: float = DEFAULT_COVERAGE_THRESHOLD,
) -> bool:
    return document_coverage_ratio(page_ratios) < threshold
