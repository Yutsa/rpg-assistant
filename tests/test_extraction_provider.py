"""Tests for raw extraction provider registry and defaults."""

from __future__ import annotations

import os

import pytest

from rpg_ingest.raw.providers import (
    DEFAULT_EXTRACTION_PROVIDER,
    resolve_extraction_provider,
)
from rpg_ingest.raw.providers.docling import DoclingExtractionProvider
from rpg_ingest.raw.providers.legacy import LegacyExtractionProvider


def test_default_extraction_provider_is_legacy() -> None:
    assert DEFAULT_EXTRACTION_PROVIDER == "legacy"


def test_resolve_extraction_provider_uses_legacy_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RPG_EXTRACTION_PROVIDER", raising=False)
    provider = resolve_extraction_provider(None)
    assert isinstance(provider, LegacyExtractionProvider)


def test_resolve_extraction_provider_honours_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RPG_EXTRACTION_PROVIDER", "docling")
    provider = resolve_extraction_provider(None)
    assert isinstance(provider, DoclingExtractionProvider)


def test_resolve_extraction_provider_explicit_docling() -> None:
    provider = resolve_extraction_provider("docling")
    assert isinstance(provider, DoclingExtractionProvider)


def test_resolve_extraction_provider_explicit_pymupdf4llm() -> None:
    provider = resolve_extraction_provider("pymupdf4llm")
    from rpg_ingest.raw.providers.pymupdf4llm import Pymupdf4LlmExtractionProvider

    assert isinstance(provider, Pymupdf4LlmExtractionProvider)
