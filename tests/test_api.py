from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from rpg_api.deps import get_raw_repo, get_semantic_repo
from rpg_api.main import create_app
from rpg_core.models.raw import (
    BBox,
    ChunkRecord,
    IngestionRunRecord,
    PageBlockRecord,
    PageRecord,
    SectionRecord,
    SourceSpan,
)
from tests.fixtures.db import memory_repo as _memory_repo_factory


def _memory_repo():
    return _memory_repo_factory(
        with_pages=True,
        with_semantic=True,
        check_same_thread=False,
    )


@pytest.fixture()
def api_client() -> TestClient:
    repo = _memory_repo()
    repo.ensure_campaign("momie", title="Momie", game_system="cof2")
    repo.upsert_document(
        "doc_test",
        campaign_id="momie",
        filename="test.pdf",
        page_count=1,
        content_hash="abc",
    )
    repo.insert_sections(
        [
            SectionRecord(
                id="sec_1",
                campaign_id="momie",
                document_id="doc_test",
                parent_section_id=None,
                title="Intro",
                level=1,
                page_start=1,
                page_end=1,
            )
        ]
    )
    repo.insert_chunks(
        [
            ChunkRecord(
                id="chunk_1",
                campaign_id="momie",
                document_id="doc_test",
                section_id="sec_1",
                page_start=1,
                page_end=1,
                text="Hello adventurer",
                chunk_type_hint="narrative",
                token_count=3,
                source_spans=[
                    SourceSpan(page=1, page_block_ids=["blk_1"], bbox=BBox(x0=10, y0=20, x1=100, y1=40))
                ],
            ),
            ChunkRecord(
                id="chunk_stat",
                campaign_id="momie",
                document_id="doc_test",
                section_id="sec_1",
                page_start=1,
                page_end=1,
                text="Gobelin NC 1",
                chunk_type_hint="stat_block",
                token_count=5,
                metadata={
                    "stat_block": {
                        "name": "Gobelin",
                        "nc": 1,
                        "attributes": {"FOR": "10"},
                        "abilities": [{"title": "Coup sournois", "text": ""}],
                    }
                },
            ),
        ]
    )
    repo.insert_pages(
        [
            PageRecord(
                id="page_1",
                document_id="doc_test",
                page_number=1,
                text="Hello",
                text_coverage_ratio=1.0,
                width=595.0,
                height=842.0,
            )
        ]
    )
    repo.insert_page_blocks(
        [
            PageBlockRecord(
                id="blk_1",
                document_id="doc_test",
                page_id="page_1",
                page_number=1,
                block_index=0,
                text="Hello",
                bbox=BBox(x0=10, y0=20, x1=100, y1=40),
            )
        ]
    )

    from rpg_core.storage.repositories.semantic import SemanticRepository

    def _override_raw_repo():
        return repo

    def _override_semantic_repo():
        return SemanticRepository(repo.conn)

    app = create_app()
    app.dependency_overrides[get_raw_repo] = _override_raw_repo
    app.dependency_overrides[get_semantic_repo] = _override_semantic_repo
    return TestClient(app)


def test_list_campaigns(api_client: TestClient) -> None:
    response = api_client.get("/campaigns")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "momie"


def test_list_documents_and_sections(api_client: TestClient) -> None:
    docs = api_client.get("/campaigns/momie/documents").json()
    assert docs[0]["id"] == "doc_test"
    sections = api_client.get("/documents/doc_test/sections").json()
    assert sections[0]["title"] == "Intro"


def test_list_and_get_chunks(api_client: TestClient) -> None:
    listed = api_client.get("/documents/doc_test/chunks", params={"section_id": "sec_1"}).json()
    assert len(listed) == 2
    detail = api_client.get("/chunks/chunk_1").json()
    assert detail["text"] == "Hello adventurer"
    assert detail["source_spans"][0]["page_block_ids"] == ["blk_1"]


def test_page_meta_and_blocks(api_client: TestClient) -> None:
    meta = api_client.get("/documents/doc_test/pages/1").json()
    assert meta["width"] == 595.0
    blocks = api_client.get("/documents/doc_test/pages/1/blocks").json()
    assert blocks[0]["id"] == "blk_1"


def test_page_nodes_with_raw_layout(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Overlay me", fontsize=14)
    doc.save(pdf_path)
    doc.close()

    document = pymupdf.open(pdf_path)
    try:
        from rpg_ingest.raw.layout import extract_raw_layout_pages

        raw_page = extract_raw_layout_pages(document)[0]
    finally:
        document.close()

    repo = _memory_repo()
    repo.ensure_campaign("momie")
    repo.upsert_document("doc_raw", "momie", "test.pdf", 1, "def")
    repo.insert_pages(
        [
            PageRecord(
                id="page_raw_1",
                document_id="doc_raw",
                page_number=1,
                text=raw_page.text,
                text_coverage_ratio=1.0,
                width=raw_page.width,
                height=raw_page.height,
                raw_layout=raw_page.raw_layout,
            )
        ]
    )
    repo.create_ingestion_run(
        IngestionRunRecord(
            id="run_raw",
            campaign_id="momie",
            document_id="doc_raw",
            stage="raw",
            status="completed",
            stats={"source_pdf_path": str(pdf_path)},
        )
    )

    def _override_raw_repo():
        return repo

    app = create_app()
    app.dependency_overrides[get_raw_repo] = _override_raw_repo
    client = TestClient(app)

    raw_layout = client.get("/documents/doc_raw/pages/1/raw-layout").json()
    assert raw_layout.get("blocks")

    nodes = client.get("/documents/doc_raw/pages/1/nodes", params={"level": "block"}).json()
    assert len(nodes) >= 1
    assert nodes[0]["depth"] == "block"
    assert "Overlay" in nodes[0]["text"]


def test_stat_blocks(api_client: TestClient) -> None:
    index = api_client.get("/documents/doc_test/stat-blocks").json()
    assert index[0]["name"] == "Gobelin"
    detail = api_client.get("/documents/doc_test/stat-blocks/Gobelin").json()
    assert detail["nc"] == 1
    assert detail["attributes"]["FOR"] == "10"
    by_chunk = api_client.get("/documents/doc_test/stat-blocks/chunk_stat").json()
    assert by_chunk["name"] == "Gobelin"


def test_render_page_with_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Render me")
    doc.save(pdf_path)
    doc.close()

    repo = _memory_repo()
    repo.ensure_campaign("momie")
    repo.upsert_document("doc_test", "momie", "test.pdf", 1, "abc")
    repo.create_ingestion_run(
        IngestionRunRecord(
            id="run_1",
            campaign_id="momie",
            document_id="doc_test",
            stage="raw",
            status="completed",
            stats={"source_pdf_path": str(pdf_path)},
        )
    )
    repo.insert_pages(
        [
            PageRecord(
                id="page_1",
                document_id="doc_test",
                page_number=1,
                text="x",
                text_coverage_ratio=1.0,
                width=595.0,
                height=842.0,
            )
        ]
    )

    def _override_raw_repo():
        return repo

    app = create_app()
    app.dependency_overrides[get_raw_repo] = _override_raw_repo
    client = TestClient(app)
    response = client.get("/documents/doc_test/pages/1/render", params={"dpi": 72})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
