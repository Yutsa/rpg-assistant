"""Registry and resolution for raw extraction providers."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from rpg_ingest.raw.providers.base import RawExtractionProvider
from rpg_ingest.raw.providers.legacy import LegacyExtractionProvider

if TYPE_CHECKING:
    from rpg_ingest.raw.providers.docling import DoclingProviderOptions

DEFAULT_EXTRACTION_PROVIDER = "legacy"
_ENV_VAR = "RPG_EXTRACTION_PROVIDER"

_PROVIDERS: dict[str, str] = {
    "legacy": "legacy",
    "docling": "docling",
}


def resolve_extraction_provider(
    name: str | None = None,
    *,
    docling_options: DoclingProviderOptions | None = None,
) -> RawExtractionProvider:
    """Resolve a provider by name, env var, or default."""
    provider_name = (name or os.environ.get(_ENV_VAR) or DEFAULT_EXTRACTION_PROVIDER).lower()
    if provider_name not in _PROVIDERS:
        raise ValueError(
            f"Unknown extraction provider {provider_name!r}; "
            f"expected one of {sorted(_PROVIDERS)}"
        )
    if provider_name == "docling":
        from rpg_ingest.raw.providers.docling import DoclingExtractionProvider

        return DoclingExtractionProvider(docling_options)
    return LegacyExtractionProvider()
