from __future__ import annotations

from typing import Protocol

from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage

from rpg_assistant.ingestion.raw.stat_blocks.types import ParsedStatBlock, StatBlockSpan


class StatBlockProfile(Protocol):
    @property
    def profile_id(self) -> str: ...

    @property
    def aliases(self) -> list[str]: ...

    def matches_document(self, pages: list[LayoutPage]) -> bool: ...

    def is_false_heading(
        self,
        block: LayoutBlock,
        page_blocks: list[LayoutBlock],
        block_idx: int,
    ) -> bool: ...

    def detect_spans(self, pages: list[LayoutPage]) -> list[StatBlockSpan]: ...

    def parse_span(self, span: StatBlockSpan) -> ParsedStatBlock: ...

    def normalize_block_text(self, text: str) -> str: ...

    def chunk_type_hint(self, text: str, blocks: list[LayoutBlock]) -> str | None: ...
