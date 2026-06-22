from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from rpg_ingest.feedback.extractor_compare import (
    clear_compare_cache,
    compare_page_extractors,
    reset_clojure_pdfbox_session,
)
from rpg_ingest.raw.extractor_compare_ingest import (
    COMPARE_LANE_PDFBOX,
    COMPARE_LANE_PYMUPDF,
)
from rpg_ingest.raw.importer import INGEST_MODE_EXTRACTOR_COMPARE, run
from rpg_core.storage.db import get_connection
from rpg_core.storage.repositories.raw import RawRepository


@pytest.fixture(autouse=True)
def _reset_extractor_runtime():
    clear_compare_cache()
    reset_clojure_pdfbox_session()
    yield
    clear_compare_cache()
    reset_clojure_pdfbox_session()


def _make_text_pdf(path: Path, lines: list[str]) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72.0
    for line in lines:
        page.insert_text((72, y), line, fontsize=12)
        y += 24
    doc.save(path)
    doc.close()


def test_extractor_compare_import_persists_both_lanes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "compare.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    pdf_path = tmp_path / "compare.pdf"
    filler = "Extractor compare import test. " * 80
    _make_text_pdf(pdf_path, [filler, filler])

    from rpg_core.storage import db as db_module

    db_module._engine = None

    from alembic import command
    from alembic.config import Config

    cfg = Config("/workspace/alembic.ini")
    command.upgrade(cfg, "head")

    result = run(
        pdf_path,
        campaign_id="compare-campaign",
        ingest_mode=INGEST_MODE_EXTRACTOR_COMPARE,
        coverage_threshold=0.0,
    )
    assert result.status == "completed"
    assert result.document_id is not None
    assert result.stats["ingest_mode"] == INGEST_MODE_EXTRACTOR_COMPARE
    assert result.stats["pymupdf_block_count"] >= 1
    assert result.stats["pdfbox_block_count"] >= 1
    assert result.stats["section_count"] == 0
    assert result.stats["chunk_count"] == 0

    with get_connection() as conn:
        repo = RawRepository(conn)
        page = repo.get_page(result.document_id, 1)
        assert page is not None
        assert page.extraction_method == "extractor_compare"

        blocks = repo.list_page_blocks_for_page(result.document_id, 1)
        lanes = {(block.metadata or {}).get("compare_lane") for block in blocks}
        assert COMPARE_LANE_PYMUPDF in lanes
        assert COMPARE_LANE_PDFBOX in lanes

        db_compare = compare_page_extractors(
            pdf_path,
            1,
            repo=repo,
            document_id=result.document_id,
        )
    assert db_compare["source"] == "database"
    assert len(db_compare["pymupdf"]["blocks"]) >= 1
    assert len(db_compare["pdfbox"]["blocks"]) >= 1
