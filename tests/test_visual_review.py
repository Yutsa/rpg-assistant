from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from rpg_assistant.ingestion.feedback.visual_review import (
    VisualReviewError,
    build_visual_review_sample,
    resolve_pdf_path,
)
from rpg_assistant.models.raw import ChunkRecord, SectionRecord, SourceSpan
from rpg_assistant.models.raw import IngestionRunRecord
from rpg_assistant.storage.repositories.raw import RawRepository
from tests.fixtures.db import memory_repo as _memory_repo


def _section(section_id: str, title: str, page_start: int, page_end: int) -> SectionRecord:
    return SectionRecord(
        id=section_id,
        campaign_id="camp",
        document_id="doc_1",
        title=title,
        level=1,
        page_start=page_start,
        page_end=page_end,
    )


def _chunk(
    chunk_id: str,
    section_id: str,
    page_start: int,
    page_end: int,
    *,
    span_pages: list[int] | None = None,
) -> ChunkRecord:
    pages = span_pages or [page_start]
    return ChunkRecord(
        id=chunk_id,
        campaign_id="camp",
        document_id="doc_1",
        section_id=section_id,
        page_start=page_start,
        page_end=page_end,
        text=f"Text for {chunk_id}",
        token_count=10,
        source_spans=[
            SourceSpan(page=page, page_block_ids=[f"block_{page:03d}_000"])
            for page in pages
        ],
    )


def test_build_visual_review_sample_is_deterministic() -> None:
    sections = [
        _section("sec_a", "Alpha", 1, 2),
        _section("sec_b", "Beta", 3, 4),
        _section("sec_c", "Gamma", 5, 6),
    ]
    chunks_by_section = {
        "sec_a": [_chunk("chunk_a1", "sec_a", 1, 1), _chunk("chunk_a2", "sec_a", 2, 2)],
        "sec_b": [_chunk("chunk_b1", "sec_b", 3, 3)],
        "sec_c": [_chunk("chunk_c1", "sec_c", 5, 6, span_pages=[5, 6])],
    }

    first = build_visual_review_sample(
        sections,
        chunks_by_section,
        section_count=2,
        chunks_per_section=1,
        seed=7,
        max_pages=20,
    )
    second = build_visual_review_sample(
        sections,
        chunks_by_section,
        section_count=2,
        chunks_per_section=1,
        seed=7,
        max_pages=20,
    )

    assert first.seed == 7
    assert len(first.samples) == 2
    assert [s.section.id for s in first.samples] == [s.section.id for s in second.samples]
    assert [c.id for s in first.samples for c in s.chunks] == [
        c.id for s in second.samples for c in s.chunks
    ]


def test_build_visual_review_sample_truncates_pages() -> None:
    sections = [_section("sec_a", "Alpha", 1, 10)]
    chunks_by_section = {
        "sec_a": [
            _chunk("chunk_a1", "sec_a", 1, 10, span_pages=list(range(1, 11))),
        ],
    }

    sample = build_visual_review_sample(
        sections,
        chunks_by_section,
        section_count=1,
        chunks_per_section=1,
        seed=1,
        max_pages=3,
    )

    assert sample.pages_truncated is True
    assert len(sample.all_pages) == 3


def test_resolve_pdf_path_from_latest_run(tmp_path: Path) -> None:
    pdf_path = tmp_path / "book.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 minimal")

    repo = _memory_repo()
    repo.ensure_campaign("camp")
    repo.upsert_document("doc_1", "camp", "book.pdf", 1, "hash")
    repo.create_ingestion_run(
        IngestionRunRecord(
            id="run_1",
            campaign_id="camp",
            document_id="doc_1",
            stage="raw",
            status="completed",
            stats={"source_pdf_path": str(pdf_path.resolve())},
        )
    )

    resolved = resolve_pdf_path(repo, "doc_1")
    assert resolved == pdf_path.resolve()


def test_resolve_pdf_path_override(tmp_path: Path) -> None:
    pdf_path = tmp_path / "override.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 minimal")

    repo = _memory_repo()
    resolved = resolve_pdf_path(repo, "doc_missing", pdf_path_override=pdf_path)
    assert resolved == pdf_path.resolve()


def test_resolve_pdf_path_missing_raises() -> None:
    repo = _memory_repo()
    with pytest.raises(VisualReviewError, match="No source_pdf_path"):
        resolve_pdf_path(repo, "doc_missing")


def test_get_latest_raw_run_and_list_chunks_for_sections() -> None:
    repo = _memory_repo()
    repo.ensure_campaign("camp")
    repo.upsert_document("doc_1", "camp", "book.pdf", 5, "hash")
    repo.create_ingestion_run(
        IngestionRunRecord(
            id="run_old",
            campaign_id="camp",
            document_id="doc_1",
            stage="raw",
            status="completed",
            stats={"source_pdf_path": "/old/path.pdf"},
        )
    )
    repo.create_ingestion_run(
        IngestionRunRecord(
            id="run_new",
            campaign_id="camp",
            document_id="doc_1",
            stage="raw",
            status="completed",
            stats={"source_pdf_path": "/new/path.pdf"},
        )
    )

    latest = repo.get_latest_raw_run("doc_1")
    assert latest is not None
    assert latest.id == "run_new"
    assert latest.stats["source_pdf_path"] == "/new/path.pdf"

    repo.insert_sections([_section("sec_a", "A", 1, 2)])
    repo.insert_chunks(
        [
            _chunk("chunk_a1", "sec_a", 1, 1),
            _chunk("chunk_a2", "sec_a", 2, 2),
        ]
    )

    grouped = repo.list_chunks_for_sections("doc_1", ["sec_a"])
    assert len(grouped["sec_a"]) == 2


def test_import_persists_source_pdf_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from rpg_assistant.ingestion.raw.importer import run as import_run

    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    import sqlite3

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(Path("migrations")))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(alembic_cfg, "head")

    pdf_path = tmp_path / "adventure.pdf"
    document = pymupdf.open()
    page = document.new_page()
    body = (
        "CHAPTER ONE\n\nThe heroes arrive at the ancient tomb with torches lit. "
        "They explore dusty corridors and read faded inscriptions on the walls. "
    ) * 80
    page.insert_text((72, 72), body)
    document.save(pdf_path)
    document.close()

    result = import_run(pdf_path, campaign_id="test-camp", coverage_threshold=0.01)
    assert result.status == "completed"
    assert result.stats["source_pdf_path"] == str(pdf_path.resolve())

    connection = sqlite3.connect(db_path)
    row = connection.execute(
        "SELECT stats FROM ingestion_runs WHERE id = ?",
        (result.ingestion_run_id,),
    ).fetchone()
    connection.close()
    stats = json.loads(row[0])
    assert stats["source_pdf_path"] == str(pdf_path.resolve())
