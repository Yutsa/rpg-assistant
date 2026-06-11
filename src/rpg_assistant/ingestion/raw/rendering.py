from __future__ import annotations

from pathlib import Path

import pymupdf


def default_cache_dir(document_id: str) -> Path:
    return Path("data/page_renders") / document_id


def _cache_path(cache_dir: Path, page_number: int, dpi: int) -> Path:
    return cache_dir / f"page_{page_number:04d}_{dpi}.png"


def render_pdf_pages(
    pdf_path: Path,
    page_numbers: list[int],
    *,
    document_id: str,
    dpi: int = 150,
    cache_dir: Path | None = None,
) -> dict[int, Path]:
    """Render PDF pages to PNG files, using a disk cache when possible."""
    if not page_numbers:
        return {}

    resolved_pdf = pdf_path.resolve()
    if not resolved_pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {resolved_pdf}")

    target_cache = (cache_dir or default_cache_dir(document_id)).resolve()
    target_cache.mkdir(parents=True, exist_ok=True)

    pdf_mtime = resolved_pdf.stat().st_mtime
    unique_pages = sorted(set(page_numbers))
    rendered: dict[int, Path] = {}

    with pymupdf.open(resolved_pdf) as document:
        page_count = document.page_count
        for page_number in unique_pages:
            if page_number < 1 or page_number > page_count:
                raise ValueError(
                    f"Page {page_number} out of range (document has {page_count} pages)"
                )

            output_path = _cache_path(target_cache, page_number, dpi)
            if output_path.is_file() and output_path.stat().st_mtime >= pdf_mtime:
                rendered[page_number] = output_path
                continue

            page = document[page_number - 1]
            matrix = pymupdf.Matrix(dpi / 72, dpi / 72)
            pixmap = page.get_pixmap(matrix=matrix)
            pixmap.save(str(output_path))
            rendered[page_number] = output_path

    return rendered
