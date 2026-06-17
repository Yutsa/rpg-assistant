from __future__ import annotations

import re

from rpg_assistant.ingestion.raw.layout import LayoutBlock, LayoutPage

from rpg_assistant.ingestion.raw.stat_blocks.types import ParsedStatBlock, StatBlockSpan

TABLE_RE = re.compile(r"(\|.+\|)|(\bAC\b|\bHP\b|\bSpeed\b)", re.IGNORECASE)
STAT_BLOCK_RE = re.compile(
    r"\b(armor class|hit points|challenge rating)\b", re.IGNORECASE
)


class GenericStatBlockProfile:
    profile_id = "generic"
    aliases: list[str] = []

    def matches_document(self, pages: list[LayoutPage]) -> bool:
        return False

    def is_false_heading(
        self,
        block: LayoutBlock,
        page_blocks: list[LayoutBlock],
        block_idx: int,
    ) -> bool:
        return block.metadata.get("stat_block_role") in {"header", "stats", "icon"}

    def detect_spans(self, pages: list[LayoutPage]) -> list[StatBlockSpan]:
        return []

    def parse_span(self, span: StatBlockSpan) -> ParsedStatBlock:
        text = "\n\n".join(block.text for block in span.blocks)
        return ParsedStatBlock(
            name="",
            raw_text=text,
            game_system=self.profile_id,
        )

    def normalize_block_text(self, text: str) -> str:
        return text

    def chunk_type_hint(self, text: str, blocks: list[LayoutBlock]) -> str | None:
        if STAT_BLOCK_RE.search(text) or TABLE_RE.search(text):
            return "stat_block"
        if len(blocks) <= 3 and max((len(b.text) for b in blocks), default=0) < 80:
            return "table"
        return None
