from __future__ import annotations

from rpg_assistant.ingestion.raw.layout import LayoutPage
from rpg_assistant.ingestion.raw.stat_blocks.cof2 import Cof2StatBlockProfile
from rpg_assistant.ingestion.raw.stat_blocks.generic import GenericStatBlockProfile
from rpg_assistant.ingestion.raw.stat_blocks.profile import StatBlockProfile

_PROFILES: list[StatBlockProfile] = [
    Cof2StatBlockProfile(),
    GenericStatBlockProfile(),
]

_ALIAS_MAP: dict[str, StatBlockProfile] = {}
for _profile in _PROFILES:
    for _alias in _profile.aliases:
        _ALIAS_MAP[_alias.lower().strip()] = _profile


def register_profile(profile: StatBlockProfile) -> None:
    _PROFILES.insert(0, profile)
    for alias in profile.aliases:
        _ALIAS_MAP[alias.lower().strip()] = profile


def resolve_profile(
    game_system: str,
    pages: list[LayoutPage] | None = None,
) -> StatBlockProfile:
    normalized = game_system.lower().strip()
    if normalized and normalized in _ALIAS_MAP:
        return _ALIAS_MAP[normalized]

    if pages:
        for profile in _PROFILES:
            if profile.profile_id == "generic":
                continue
            if profile.matches_document(pages):
                return profile

    for profile in _PROFILES:
        if profile.profile_id == "generic":
            return profile

    return GenericStatBlockProfile()
