"""Extraction provider protocol for the raw PDF pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from rpg_ingest.raw.layout import LayoutPage


@dataclass
class ExtractionResult:
    """Output of a raw extraction provider."""

    pages: list[LayoutPage]
    extraction_method: str = "pymupdf"
    provider_id: str = "legacy"
    metadata: dict[str, Any] = field(default_factory=dict)


class RawExtractionProvider(Protocol):
    """Convert a PDF into layout pages."""

    provider_id: str

    def extract(self, pdf_path: Path) -> ExtractionResult: ...
