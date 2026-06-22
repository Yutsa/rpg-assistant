"""API tests for live PyMuPDF vs PDFBox raw extractor comparison."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from rpg_api.deps import get_raw_repo
from rpg_api.main import create_app
from rpg_core.models.raw import BBox, IngestionRunRecord, PageBlockRecord, PageRecord
from rpg_ingest.feedback.extractor_compare import (
    clear_compare_cache,
    compare_page_extractors,
    reset_clojure_pdfbox_session,
)
from rpg_ingest.raw.extractor_compare_ingest import COMPARE_LANE_PDFBOX, COMPARE_LANE_PYMUPDF
from tests.fixtures.db import memory_repo as _memory_repo_factory


@pytest.fixture(autouse=True)
def _reset_extractor_runtime():
    clear_compare_cache()
    reset_clojure_pdfbox_session()
    yield
    clear_compare_cache()
    reset_clojure_pdfbox_session()


def _write_text_pdf(path: Path, *, pages: int = 1) -> None:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Extractor compare page {i + 1}", fontsize=14)
        page.insert_text((72, 100), "Second line for PDFBox stripper.", fontsize=11)
    doc.save(path)
    doc.close()


@pytest.fixture
def compare_client(tmp_path: Path):
    pdf_path = tmp_path / "compare.pdf"
    _write_text_pdf(pdf_path)

    repo = _memory_repo_factory(with_pages=True, check_same_thread=False)
    repo.ensure_campaign("cmp", title="Compare", game_system="generic")
    repo.upsert_document("doc_cmp", "cmp", "compare.pdf", 1, "hash")
    repo.insert_pages(
        [
            PageRecord(
                id="page_cmp_1",
                document_id="doc_cmp",
                page_number=1,
                text="Extractor compare page 1",
                text_coverage_ratio=1.0,
                width=595.0,
                height=842.0,
            )
        ]
    )
    repo.create_ingestion_run(
        IngestionRunRecord(
            id="run_cmp",
            campaign_id="cmp",
            document_id="doc_cmp",
            stage="raw",
            status="completed",
            stats={"source_pdf_path": str(pdf_path)},
        )
    )

    def _override_raw_repo():
        return repo

    app = create_app()
    app.dependency_overrides[get_raw_repo] = _override_raw_repo
    with TestClient(app) as client:
        yield client, pdf_path


def test_extractors_compare_endpoint(compare_client):
    client, _pdf_path = compare_client
    response = client.get("/documents/doc_cmp/pages/1/extractors-compare")
    assert response.status_code == 200
    body = response.json()
    assert body["page_number"] == 1
    assert body["pymupdf"]["extraction_method"] == "pymupdf_raw"
    assert body["pdfbox"]["extraction_method"] == "pdfbox"
    assert len(body["pymupdf"]["blocks"]) >= 1
    assert len(body["pdfbox"]["blocks"]) >= 1
    assert body["pymupdf"]["blocks"][0]["text"]
    assert "bbox" in body["pymupdf"]["blocks"][0]


def test_extractors_compare_endpoint_from_db(compare_client):
    client, pdf_path = compare_client
    repo = _memory_repo_factory(with_pages=True, check_same_thread=False)
    repo.ensure_campaign("cmp", title="Compare", game_system="generic")
    repo.upsert_document("doc_db", "cmp", "compare.pdf", 1, "hash-db")
    repo.insert_pages(
        [
            PageRecord(
                id="page_db_1",
                document_id="doc_db",
                page_number=1,
                text="Stored compare page",
                extraction_method="extractor_compare",
                text_coverage_ratio=1.0,
                width=595.0,
                height=842.0,
            )
        ]
    )
    repo.insert_page_blocks(
        [
            PageBlockRecord(
                id="pymupdf_doc_db_0001_0000",
                document_id="doc_db",
                page_id="page_db_1",
                page_number=1,
                block_index=0,
                text="Stored pymupdf block",
                bbox=BBox(x0=72, y0=72, x1=200, y1=90),
                metadata={"compare_lane": COMPARE_LANE_PYMUPDF, "source": "pymupdf_raw"},
            ),
            PageBlockRecord(
                id="pdfbox_doc_db_0001_0000",
                document_id="doc_db",
                page_id="page_db_1",
                page_number=1,
                block_index=0,
                text="Stored pdfbox block",
                bbox=BBox(x0=72, y0=72, x1=200, y1=90),
                metadata={"compare_lane": COMPARE_LANE_PDFBOX, "source": "pdfbox_raw"},
            ),
        ]
    )
    repo.create_ingestion_run(
        IngestionRunRecord(
            id="run_db",
            campaign_id="cmp",
            document_id="doc_db",
            stage="raw",
            status="completed",
            stats={"source_pdf_path": str(pdf_path)},
        )
    )

    app = create_app()

    def _override_raw_repo():
        return repo

    app.dependency_overrides[get_raw_repo] = _override_raw_repo
    with TestClient(app) as db_client:
        response = db_client.get("/documents/doc_db/pages/1/extractors-compare")
    assert response.status_code == 200
    body = response.json()
    assert body["pymupdf"]["blocks"][0]["text"] == "Stored pymupdf block"
    assert body["pdfbox"]["blocks"][0]["text"] == "Stored pdfbox block"


def test_clojure_raw_extract_document_cli(tmp_path: Path):
    pdf_path = tmp_path / "raw-document.pdf"
    _write_text_pdf(pdf_path, pages=2)
    clj_root = Path(__file__).resolve().parents[1] / "packages" / "ingest-clj"
    result = subprocess.run(
        ["clojure", "-M:ingest", "raw", "extract-document", "--pdf", str(pdf_path)],
        cwd=clj_root,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["page_count"] == 2
    assert len(payload["pages"]) == 2
    assert payload["pages"][0]["blocks"]


def test_clojure_raw_extract_page_cli(tmp_path: Path):
    pdf_path = tmp_path / "raw-page.pdf"
    _write_text_pdf(pdf_path)
    clj_root = Path(__file__).resolve().parents[1] / "packages" / "ingest-clj"
    result = subprocess.run(
        ["clojure", "-M:ingest", "raw", "extract-page", "--pdf", str(pdf_path), "--page", "1"],
        cwd=clj_root,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["page_number"] == 1
    assert len(payload["blocks"]) >= 1
    assert payload["blocks"][0]["text"]


def test_clojure_serve_extract_page(tmp_path: Path):
    pdf_path = tmp_path / "serve-page.pdf"
    _write_text_pdf(pdf_path)
    clj_root = Path(__file__).resolve().parents[1] / "packages" / "ingest-clj"
    process = subprocess.Popen(
        ["clojure", "-M:ingest", "serve"],
        cwd=clj_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        ready_line = process.stdout.readline()
        ready_payload = json.loads(ready_line)
        assert ready_payload["ready"] is True

        request = json.dumps({"pdf": str(pdf_path), "page": 1})
        process.stdin.write(f"{request}\n")
        process.stdin.flush()

        payload = json.loads(process.stdout.readline())
        assert payload["page_number"] == 1
        assert len(payload["blocks"]) >= 1
        assert payload["blocks"][0]["text"]
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_compare_page_extractors_uses_cache(tmp_path: Path):
    pdf_path = tmp_path / "cached.pdf"
    _write_text_pdf(pdf_path)

    first = compare_page_extractors(pdf_path, 1)
    second = compare_page_extractors(pdf_path, 1)

    assert first is second
