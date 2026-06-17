from __future__ import annotations

import unicodedata
from typing import Any


def normalize_stat_block_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().casefold())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def apply_stat_block_lookup_keys(stat_block: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(stat_block)
    name = stat_block.get("name")
    if isinstance(name, str) and name.strip():
        enriched["_lookup_name"] = normalize_stat_block_key(name)
    subtitle = stat_block.get("subtitle")
    if isinstance(subtitle, str) and subtitle.strip():
        enriched["_lookup_subtitle"] = normalize_stat_block_key(subtitle)
    return enriched


def enrich_chunk_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    stat_block = metadata.get("stat_block")
    if not isinstance(stat_block, dict):
        return metadata
    enriched = dict(metadata)
    enriched["stat_block"] = apply_stat_block_lookup_keys(stat_block)
    return enriched


def matches_stat_block_name(query: str, stat_block: dict[str, Any]) -> bool:
    key = normalize_stat_block_key(query)
    if not key:
        return False
    lookup_name = stat_block.get("_lookup_name")
    lookup_subtitle = stat_block.get("_lookup_subtitle")
    if lookup_name == key or lookup_subtitle == key:
        return True
    for field in ("name", "subtitle"):
        candidate = stat_block.get(field)
        if isinstance(candidate, str) and normalize_stat_block_key(candidate) == key:
            return True
    return False
