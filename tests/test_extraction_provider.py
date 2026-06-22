"""Tests for raw extraction provider registry and defaults."""

from __future__ import annotations

import pytest

from rpg_ingest.raw.providers import (
    DEFAULT_EXTRACTION_PROVIDER,
    resolve_extraction_provider,
)
from rpg_ingest.raw.providers.legacy import LegacyExtractionProvider


def test_default_extraction_provider_is_legacy() -> None:
    assert DEFAULT_EXTRACTION_PROVIDER == "legacy"


def test_resolve_extraction_provider_returns_legacy() -> None:
    provider = resolve_extraction_provider(None)
    assert isinstance(provider, LegacyExtractionProvider)


def test_resolve_extraction_provider_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="docling"):
        resolve_extraction_provider("docling")
