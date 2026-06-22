"""Registry and resolution for raw extraction providers."""

from __future__ import annotations

from rpg_ingest.raw.providers.base import RawExtractionProvider
from rpg_ingest.raw.providers.legacy import LegacyExtractionProvider

DEFAULT_EXTRACTION_PROVIDER = "legacy"


def resolve_extraction_provider(name: str | None = None) -> RawExtractionProvider:
    """Resolve the legacy PyMuPDF extraction provider."""
    if name is not None and name.lower() != DEFAULT_EXTRACTION_PROVIDER:
        raise ValueError(
            f"Unknown extraction provider {name!r}; "
            f"only {DEFAULT_EXTRACTION_PROVIDER!r} is supported"
        )
    return LegacyExtractionProvider()
