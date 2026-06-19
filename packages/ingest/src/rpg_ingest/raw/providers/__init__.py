"""Registry and resolution for raw extraction providers."""

from __future__ import annotations

import os

from rpg_ingest.raw.providers.base import RawExtractionProvider
from rpg_ingest.raw.providers.docling import DoclingExtractionProvider, DoclingProviderOptions
from rpg_ingest.raw.providers.legacy import LegacyExtractionProvider
from rpg_ingest.raw.providers.pymupdf4llm import Pymupdf4LlmExtractionProvider

DEFAULT_EXTRACTION_PROVIDER = "legacy"
_ENV_VAR = "RPG_EXTRACTION_PROVIDER"
_LEGACY_ENV_VAR = "RPG_INGEST_EXTRACTOR"

_PROVIDERS: dict[str, type] = {
    "legacy": LegacyExtractionProvider,
    "docling": DoclingExtractionProvider,
    "pymupdf4llm": Pymupdf4LlmExtractionProvider,
}


def resolve_extraction_provider(
    name: str | None = None,
    *,
    docling_options: DoclingProviderOptions | None = None,
) -> RawExtractionProvider:
    """Resolve a provider by name, env var, or default."""
    if name:
        provider_name = name.lower()
    elif os.environ.get(_ENV_VAR):
        provider_name = os.environ.get(_ENV_VAR, "").lower()
    elif os.environ.get(_LEGACY_ENV_VAR):
        provider_name = _normalize_legacy_extractor_env(os.environ.get(_LEGACY_ENV_VAR))
    else:
        provider_name = DEFAULT_EXTRACTION_PROVIDER

    if provider_name not in _PROVIDERS:
        raise ValueError(
            f"Unknown extraction provider {provider_name!r}; "
            f"expected one of {sorted(_PROVIDERS)}"
        )
    cls = _PROVIDERS[provider_name]
    if cls is DoclingExtractionProvider:
        return DoclingExtractionProvider(docling_options)
    return cls()


def _normalize_legacy_extractor_env(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"legacy", "pymupdf", "default", ""}:
        return "legacy"
    if normalized in {"pymupdf4llm", "llm", "layout"}:
        return "pymupdf4llm"
    if normalized == "docling":
        return "docling"
    raise ValueError(
        f"Unknown RPG_INGEST_EXTRACTOR {value!r}; "
        f"expected legacy, docling, or pymupdf4llm"
    )
