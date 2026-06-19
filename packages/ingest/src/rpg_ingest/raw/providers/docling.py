"""Docling-based extraction provider."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from rpg_ingest.raw.docling_convert import docling_document_to_layout
from rpg_ingest.raw.docling_enrich import enrich_docling_with_pymupdf
from rpg_ingest.raw.layout import extract_layout_pages
from rpg_ingest.raw.providers.base import ExtractionResult

_logger = logging.getLogger(__name__)


@dataclass
class DoclingProviderOptions:
    """Runtime options for the Docling extraction provider.

    Cost notes (see also packages/ingest/README.md):
    - Pulls heavy deps: PyTorch, transformers, RapidOCR models (~hundreds of MB).
    - First run downloads layout/table models from Hugging Face / ModelScope.
    - CPU-only by default; GPU accelerates layout models when available.
    - ``do_ocr=True`` enables RapidOCR (extra models, slower); keep False for
      text-native PDFs. Docling is MIT-licensed; bundled OCR models have their
      own licenses (RapidOCR / Paddle).
    """

    do_ocr: bool = False
    do_table_structure: bool = True
    force_backend_text: bool = True
    document_timeout: float | None = 120.0


class DoclingExtractionProvider:
    """Extract layout and structure using IBM Docling."""

    provider_id = "docling"

    def __init__(self, options: DoclingProviderOptions | None = None) -> None:
        self.options = options or DoclingProviderOptions()
        self._converter: DocumentConverter | None = None

    def _get_converter(self) -> DocumentConverter:
        if self._converter is None:
            pipeline_options = PdfPipelineOptions(
                do_ocr=self.options.do_ocr,
                do_table_structure=self.options.do_table_structure,
                force_backend_text=self.options.force_backend_text,
                document_timeout=self.options.document_timeout,
            )
            self._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
        return self._converter

    def extract(self, pdf_path: Path) -> ExtractionResult:
        converter = self._get_converter()
        result = converter.convert(str(pdf_path))
        doc = result.document
        docling_elements, _docling_pages = docling_document_to_layout(doc)

        pymupdf_document = pymupdf.open(pdf_path)
        try:
            pymupdf_pages = extract_layout_pages(pymupdf_document)
        finally:
            pymupdf_document.close()

        elements, pages = enrich_docling_with_pymupdf(docling_elements, pymupdf_pages)
        metadata: dict[str, Any] = {
            "docling_page_count": len(doc.pages),
            "docling_element_count": len(docling_elements),
            "enriched_element_count": len(elements),
            "enriched_block_count": sum(len(page.blocks) for page in pages),
            "do_ocr": self.options.do_ocr,
            "force_backend_text": self.options.force_backend_text,
        }
        if hasattr(result, "timings") and result.timings:
            metadata["timings"] = dict(result.timings)
        return ExtractionResult(
            pages=pages,
            elements=elements,
            extraction_method="docling",
            provider_id=self.provider_id,
            metadata=metadata,
        )
