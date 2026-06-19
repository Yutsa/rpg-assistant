"""Stable internal document elements produced by extraction providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rpg_core.models.raw import BBox

# Content-bearing element types included in chunks.
CONTENT_ELEMENT_TYPES = frozenset(
    {
        "paragraph",
        "list_item",
        "table",
        "figure",
        "caption",
        "code",
        "formula",
        "key_value",
        "handwritten",
    }
)

# Section-heading element types.
HEADING_ELEMENT_TYPES = frozenset({"title", "heading"})

# Elements excluded from sections and chunks.
SKIP_ELEMENT_TYPES = frozenset({"page_header", "page_footer", "marker", "empty"})


@dataclass
class DocElement:
    """Provider-neutral document element in logical reading order."""

    element_index: int
    element_type: str
    text: str
    page_number: int
    block_index: int
    bbox: BBox
    heading_level: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_heading(self) -> bool:
        return self.element_type in HEADING_ELEMENT_TYPES

    @property
    def is_content(self) -> bool:
        return self.element_type in CONTENT_ELEMENT_TYPES

    @property
    def is_skipped(self) -> bool:
        return self.element_type in SKIP_ELEMENT_TYPES

    @property
    def position(self) -> tuple[int, int]:
        return (self.page_number, self.block_index)
