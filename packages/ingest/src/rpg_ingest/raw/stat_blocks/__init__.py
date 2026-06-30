from __future__ import annotations

from dataclasses import dataclass

from rpg_ingest.raw.layout import LayoutPage
from rpg_ingest.raw.stat_blocks.profile import StatBlockProfile
from rpg_ingest.raw.stat_blocks.registry import resolve_profile
from rpg_ingest.raw.stat_blocks.types import (
    ParsedStatBlock,
    StatBlockAnnotationResult,
    StatBlockSpan,
)

__all__ = [
    "GameSystemInfo",
    "ParsedStatBlock",
    "StatBlockAnnotationResult",
    "StatBlockProfile",
    "StatBlockSpan",
    "annotate_stat_blocks",
    "known_game_system_ids",
    "list_importable_game_systems",
    "resolve_profile",
]


@dataclass(frozen=True)
class GameSystemInfo:
    id: str
    label: str
    description: str = ""
    supports_stat_blocks: bool = False
    default: bool = False


_GAME_SYSTEM_CATALOG: tuple[GameSystemInfo, ...] = (
    GameSystemInfo(
        id="cof2",
        label="Chroniques Oubliées Fantasy 2",
        description="Fiches monstre/PNJ COF2 (NC, attributs, attaques, capacités)",
        supports_stat_blocks=True,
        default=True,
    ),
)


def list_importable_game_systems() -> list[GameSystemInfo]:
    return list(_GAME_SYSTEM_CATALOG)


def known_game_system_ids() -> frozenset[str]:
    return frozenset(entry.id for entry in _GAME_SYSTEM_CATALOG)


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
