from __future__ import annotations

import unicodedata
from typing import Any


def normalize_stat_block_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().casefold())
    return "".join(c for c in normalized if not unicodedata.combining(c))


def matches_stat_block_name(query: str, stat_block: dict[str, Any]) -> bool:
    key = normalize_stat_block_key(query)
    if not key:
        return False
    for field in ("name", "subtitle"):
        candidate = stat_block.get(field)
        if isinstance(candidate, str) and normalize_stat_block_key(candidate) == key:
            return True
    return False
