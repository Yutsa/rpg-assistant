from __future__ import annotations

from pathlib import Path

import pymupdf

from rpg_assistant.ingestion.raw.rendering import render_pdf_pages


def _make_test_pdf(path: Path, pages: list[str]) -> None:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_render_pdf_pages_creates_png(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    cache_dir = tmp_path / "cache"
    _make_test_pdf(pdf_path, ["Page one text", "Page two text"])

    rendered = render_pdf_pages(
        pdf_path,
        [1, 2],
        document_id="doc_test",
        dpi=72,
        cache_dir=cache_dir,
    )

    assert set(rendered) == {1, 2}
    for page_number, image_path in rendered.items():
        assert image_path.exists()
        assert image_path.suffix == ".png"
        assert image_path.name == f"page_{page_number:04d}_72.png"


def test_render_pdf_pages_uses_cache(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    cache_dir = tmp_path / "cache"
    _make_test_pdf(pdf_path, ["Cached page"])

    first = render_pdf_pages(
        pdf_path,
        [1],
        document_id="doc_test",
        dpi=72,
        cache_dir=cache_dir,
    )
    mtime = first[1].stat().st_mtime

    second = render_pdf_pages(
        pdf_path,
        [1],
        document_id="doc_test",
        dpi=72,
        cache_dir=cache_dir,
    )

    assert second[1] == first[1]
    assert second[1].stat().st_mtime == mtime


def test_render_pdf_pages_rejects_out_of_range(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _make_test_pdf(pdf_path, ["Only page"])

    try:
        render_pdf_pages(pdf_path, [2], document_id="doc_test", cache_dir=tmp_path / "cache")
    except ValueError as exc:
        assert "out of range" in str(exc)
    else:
        raise AssertionError("Expected ValueError for out-of-range page")
