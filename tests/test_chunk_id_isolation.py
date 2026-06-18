from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from rpg_core.storage.db import get_connection
from rpg_core.storage.repositories.raw import RawRepository


def _make_pdf(path: Path, *, title: str, body: str) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), f"{title}\n\n{body}")
    document.save(path)
    document.close()


def test_chunk_ids_are_isolated_across_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alembic import command
    from alembic.config import Config
    from rpg_ingest.raw.importer import run as import_run

    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(Path("migrations")))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(alembic_cfg, "head")

    body_a = (
        "MARKER_ALPHA The heroes explore dusty corridors and read faded inscriptions. "
    ) * 80
    body_b = (
        "MARKER_BETA The heroes explore dusty corridors and read faded inscriptions. "
    ) * 80
    pdf_a = tmp_path / "adventure_a.pdf"
    pdf_b = tmp_path / "adventure_b.pdf"
    _make_pdf(pdf_a, title="ADVENTURE ALPHA", body=body_a)
    _make_pdf(pdf_b, title="ADVENTURE BETA", body=body_b)

    result_a = import_run(pdf_a, campaign_id="camp-a", coverage_threshold=0.01)
    result_b = import_run(pdf_b, campaign_id="camp-b", coverage_threshold=0.01)
    assert result_a.status == "completed"
    assert result_b.status == "completed"
    assert result_a.document_id != result_b.document_id

    with get_connection() as conn:
        repo = RawRepository(conn)
        chunks_a = repo.list_chunks(result_a.document_id, limit=200)
        chunks_b = repo.list_chunks(result_b.document_id, limit=200)

    assert chunks_a
    assert chunks_b
    ids_a = {chunk.id for chunk in chunks_a}
    ids_b = {chunk.id for chunk in chunks_b}
    assert ids_a.isdisjoint(ids_b)

    for chunk in chunks_a:
        assert chunk.document_id == result_a.document_id
        assert "MARKER_ALPHA" in chunk.text
        assert "MARKER_BETA" not in chunk.text

    for chunk in chunks_b:
        assert chunk.document_id == result_b.document_id
        assert "MARKER_BETA" in chunk.text
        assert "MARKER_ALPHA" not in chunk.text
