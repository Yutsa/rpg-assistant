"""PyMuPDF4LLM extraction provider."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from rpg_ingest.raw.elements import DocElement
from rpg_ingest.raw.providers.base import ExtractionResult
from rpg_ingest.raw.pymupdf4llm_extractor import (
    ExtractedElement,
    extract_document_pymupdf4llm,
)

_ELEMENT_TYPE_MAP = {
    "heading": "heading",
    "paragraph": "paragraph",
    "list": "list_item",
    "table": "table",
    "stat_block_candidate": "paragraph",
}


def elements_to_doc_elements(elements: list[ExtractedElement]) -> list[DocElement]:
    return [
        DocElement(
            element_index=element.order,
            element_type=_ELEMENT_TYPE_MAP.get(element.kind, "paragraph"),
            text=element.text,
            page_number=element.page,
            block_index=element.block_index,
            bbox=element.bbox,
            heading_level=element.level if element.kind == "heading" else None,
            metadata=dict(element.metadata),
        )
        for element in elements
    ]


class Pymupdf4LlmExtractionProvider:
    """Extract layout using PyMuPDF4LLM with legacy block reconciliation."""

    provider_id = "pymupdf4llm"

    def extract(self, pdf_path: Path) -> ExtractionResult:
        document = pymupdf.open(pdf_path)
        try:
            extraction = extract_document_pymupdf4llm(document)
        finally:
            document.close()
        return ExtractionResult(
            pages=extraction.layout_pages,
            elements=elements_to_doc_elements(extraction.elements),
            extraction_method="pymupdf4llm",
            provider_id=self.provider_id,
        )
