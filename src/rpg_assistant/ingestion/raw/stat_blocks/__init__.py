from __future__ import annotations

from rpg_assistant.ingestion.raw.layout import LayoutPage, rebuild_layout_page
from rpg_assistant.ingestion.raw.stat_blocks.profile import StatBlockProfile
from rpg_assistant.ingestion.raw.stat_blocks.registry import resolve_profile
from rpg_assistant.ingestion.raw.stat_blocks.types import (
    ParsedStatBlock,
    StatBlockAnnotationResult,
    StatBlockSpan,
)

__all__ = [
    "ParsedStatBlock",
    "StatBlockAnnotationResult",
    "StatBlockProfile",
    "StatBlockSpan",
    "annotate_stat_blocks",
    "resolve_profile",
]


def annotate_stat_blocks(
    pages: list[LayoutPage],
    profile: StatBlockProfile,
) -> StatBlockAnnotationResult:
    spans = profile.detect_spans(pages)
    annotated_pages = [
        rebuild_layout_page(page, page.blocks) for page in pages
    ]
    return StatBlockAnnotationResult(
        pages=annotated_pages,
        spans=spans,
        profile_id=profile.profile_id,
    )
