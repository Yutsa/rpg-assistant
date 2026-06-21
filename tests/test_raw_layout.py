from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from rpg_ingest.raw.importer import INGEST_MODE_LAYOUT_ONLY, run
from rpg_ingest.raw.layout import extract_raw_layout_pages
from rpg_ingest.raw.raw_nodes import flatten_raw_layout
from rpg_core.storage.db import get_connection
from rpg_core.storage.repositories.raw import RawRepository


def _make_text_pdf(path: Path, lines: list[str]) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72.0
    for line in lines:
        page.insert_text((72, y), line, fontsize=12)
        y += 24
    doc.save(path)
    doc.close()


def test_extract_raw_layout_pages_preserves_hierarchy(tmp_path: Path) -> None:
    pdf_path = tmp_path / "raw.pdf"
    _make_text_pdf(pdf_path, ["Title line", "Body paragraph text"])

    document = pymupdf.open(pdf_path)
    try:
        pages = extract_raw_layout_pages(document)
    finally:
        document.close()

    assert len(pages) == 1
    page = pages[0]
    assert page.raw_layout.get("blocks")
    assert len(page.blocks) >= 1
    nodes = flatten_raw_layout(page.raw_layout)
    depths = {node.depth for node in nodes}
    assert "block" in depths
    assert "line" in depths
    assert "span" in depths


def test_flatten_raw_layout_filters(tmp_path: Path) -> None:
    pdf_path = tmp_path / "raw.pdf"
    _make_text_pdf(pdf_path, ["Hello world"])

    document = pymupdf.open(pdf_path)
    try:
        raw_layout = extract_raw_layout_pages(document)[0].raw_layout
    finally:
        document.close()

    blocks = flatten_raw_layout(raw_layout, level="block")
    spans = flatten_raw_layout(raw_layout, level="span")
    assert blocks
    assert spans
    assert all(node.depth == "block" for node in blocks)
    assert all(node.depth == "span" for node in spans)


def test_layout_only_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    pdf_path = tmp_path / "campaign.pdf"
    filler = "Lorem ipsum dolor sit amet. " * 120
    _make_text_pdf(pdf_path, [filler, filler])

    from rpg_core.storage import db as db_module

    db_module._engine = None

    from alembic import command
    from alembic.config import Config

    cfg = Config("/workspace/alembic.ini")
    command.upgrade(cfg, "head")

    result = run(
        pdf_path,
        campaign_id="test-campaign",
        ingest_mode=INGEST_MODE_LAYOUT_ONLY,
        coverage_threshold=0.0,
    )
    assert result.status == "completed"
    assert result.document_id is not None
    assert result.stats["section_count"] == 0
    assert result.stats["chunk_count"] == 0
    assert result.stats["ingest_mode"] == INGEST_MODE_LAYOUT_ONLY

    with get_connection() as conn:
        repo = RawRepository(conn)
        page = repo.get_page(result.document_id, 1)
        assert page is not None
        assert page.raw_layout is not None
        sections = repo.list_sections(result.document_id)
        chunks = repo.list_chunks(result.document_id)
    assert sections == []
    assert chunks == []
