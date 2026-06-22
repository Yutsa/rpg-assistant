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
from rpg_core.models.raw import IngestionRunRecord, PageRecord
from tests.fixtures.db import memory_repo as _memory_repo_factory


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
    assert body["pdfbox"]["extraction_method"] == "pdfbox_raw"
    assert body["pdfbox_layout"]["extraction_method"] == "pdfbox_layout"
    assert len(body["pymupdf"]["blocks"]) >= 1
    assert len(body["pdfbox"]["blocks"]) >= 1
    assert len(body["pdfbox_layout"]["blocks"]) >= 1
    assert body["pymupdf"]["blocks"][0]["text"]
    assert "bbox" in body["pymupdf"]["blocks"][0]


def test_clojure_layout_extract_page_cli(tmp_path: Path):
    pdf_path = tmp_path / "layout-page.pdf"
    _write_text_pdf(pdf_path)
    clj_root = Path(__file__).resolve().parents[1] / "packages" / "ingest-clj"
    result = subprocess.run(
        [
            "clojure",
            "-M:ingest",
            "raw",
            "extract-layout-page",
            "--pdf",
            str(pdf_path),
            "--page",
            "1",
        ],
        cwd=clj_root,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["page_number"] == 1
    assert len(payload["blocks"]) >= 1
    assert payload["blocks"][0]["text"]


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
