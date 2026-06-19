"""Render synthetic LayoutPage fixtures to PDF for pymupdf4llm benchmarks."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from rpg_ingest.raw.layout import LayoutBlock, LayoutPage


def _font_size(block: LayoutBlock) -> float:
    return float(block.metadata.get("max_font_size") or block.metadata.get("avg_font_size") or 11)


def _is_bold(block: LayoutBlock) -> bool:
    return bool(block.metadata.get("is_bold"))


def layout_pages_to_pdf(pages: list[LayoutPage], path: Path) -> None:
    document = pymupdf.open()
    page_by_number = {page.page_number: page for page in pages}
    max_page = max(page_by_number)
    for page_number in range(1, max_page + 1):
        layout_page = page_by_number.get(page_number)
        width = layout_page.width if layout_page else 612.0
        height = layout_page.height if layout_page else 792.0
        pdf_page = document.new_page(width=width, height=height)
        if layout_page is None:
            continue
        for block in layout_page.blocks:
            font_size = _font_size(block)
            for line_index, line in enumerate(block.text.split("\n")):
                if not line.strip():
                    continue
                y = block.bbox.y0 + font_size + line_index * (font_size * 1.25)
                pdf_page.insert_text(
                    (block.bbox.x0, y),
                    line,
                    fontsize=font_size,
                    fontname="helv",
                )
    document.save(path)
    document.close()


def build_page8_layout_pdf(path: Path) -> None:
    from tests.test_page8_layout import _page8_fixture_pages

    layout_pages_to_pdf(_page8_fixture_pages(), path)


def build_momie_synopsis_pdf(path: Path) -> None:
    from tests.test_cof2_audit_chunking import _momie_cover_credits_pages

    layout_pages_to_pdf(_momie_cover_credits_pages(), path)
