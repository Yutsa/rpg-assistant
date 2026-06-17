from __future__ import annotations

from rpg_ingest.raw.layout import LayoutPage
from rpg_ingest.raw.stat_blocks.profile import StatBlockProfile
from rpg_ingest.raw.stat_blocks.registry import resolve_profile
from rpg_ingest.raw.stat_blocks.types import (
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
    return StatBlockAnnotationResult(
        pages=pages,
        spans=spans,
        profile_id=profile.profile_id,
    )
