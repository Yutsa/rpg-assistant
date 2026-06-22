"""Legacy PyMuPDF extraction provider."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from rpg_ingest.raw.layout import extract_layout_pages
from rpg_ingest.raw.providers.base import ExtractionResult


class LegacyExtractionProvider:
    """Extract layout using PyMuPDF block detection."""

    provider_id = "legacy"

    def extract(self, pdf_path: Path) -> ExtractionResult:
        document = pymupdf.open(pdf_path)
        try:
            pages = extract_layout_pages(document)
        finally:
            document.close()
        return ExtractionResult(
            pages=pages,
            extraction_method="pymupdf",
            provider_id=self.provider_id,
        )
