from __future__ import annotations

import os
from typing import Literal

ExtractorKind = Literal["legacy", "pymupdf4llm"]

DEFAULT_EXTRACTOR: ExtractorKind = "legacy"
_ENV_VAR = "RPG_INGEST_EXTRACTOR"


def normalize_extractor(value: str | None) -> ExtractorKind:
    if not value:
        return DEFAULT_EXTRACTOR
    normalized = value.strip().lower()
    if normalized in {"legacy", "pymupdf", "default"}:
        return "legacy"
    if normalized in {"pymupdf4llm", "llm", "layout"}:
        return "pymupdf4llm"
    raise ValueError(
        f"Unknown extractor {value!r}; expected 'legacy' or 'pymupdf4llm'"
    )


def resolve_extractor(cli_value: str | None = None) -> ExtractorKind:
    if cli_value:
        return normalize_extractor(cli_value)
    return normalize_extractor(os.environ.get(_ENV_VAR))
