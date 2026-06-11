from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from rpg_assistant.api.deps import get_raw_repo, get_semantic_repo
from rpg_assistant.api.main import create_app
from rpg_assistant.models.raw import (
    BBox,
    ChunkRecord,
    IngestionRunRecord,
    PageBlockRecord,
    PageRecord,
    SectionRecord,
    SourceSpan,
)
from rpg_assistant.storage.db import _SqliteConnection
from rpg_assistant.storage.dialect import Dialect
from rpg_assistant.storage.repositories.raw import RawRepository


def _memory_repo() -> RawRepository:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE campaigns (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            game_system TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            page_count INTEGER NOT NULL DEFAULT 0,
            content_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE ingestion_runs (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
            stage TEXT NOT NULL DEFAULT 'raw',
            status TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT,
            stats TEXT NOT NULL DEFAULT '{}',
            started_at TEXT,
            finished_at TEXT
        );
        CREATE TABLE pages (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            page_number INTEGER NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            extraction_method TEXT NOT NULL DEFAULT 'pymupdf',
            has_text INTEGER NOT NULL DEFAULT 1,
            text_coverage_ratio REAL NOT NULL DEFAULT 1.0,
            width REAL,
            height REAL,
            UNIQUE (document_id, page_number)
        );
        CREATE TABLE page_blocks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
            page_number INTEGER NOT NULL,
            block_index INTEGER NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            bbox_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE sections (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            parent_section_id TEXT,
            title TEXT NOT NULL,
            level INTEGER NOT NULL,
            page_start INTEGER NOT NULL,
            page_end INTEGER NOT NULL
        );
        CREATE TABLE chunks (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            section_id TEXT,
            page_start INTEGER NOT NULL,
            page_end INTEGER NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            chunk_type TEXT,
            chunk_type_hint TEXT,
            token_count INTEGER NOT NULL DEFAULT 0,
            source_spans_json TEXT NOT NULL DEFAULT '[]',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            needs_rechunk INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE entities (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            aliases_json TEXT NOT NULL DEFAULT '[]',
            summary TEXT NOT NULL DEFAULT '',
            player_safe_json TEXT NOT NULL DEFAULT '{}',
            gm_only_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            confidence REAL NOT NULL DEFAULT 0.5,
            ingestion_run_id TEXT,
            submitted_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE entity_relations (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            from_entity_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            to_entity_id TEXT NOT NULL,
            source_refs_json TEXT NOT NULL DEFAULT '[]',
            confidence REAL NOT NULL DEFAULT 0.5,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            ingestion_run_id TEXT,
            submitted_by TEXT NOT NULL DEFAULT ''
        );
        """
    )
    return RawRepository(_SqliteConnection(connection, Dialect("sqlite")))


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
                        "abilities": ["Coup sournois"],
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

    from rpg_assistant.storage.repositories.semantic import SemanticRepository

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


def test_stat_blocks(api_client: TestClient) -> None:
    index = api_client.get("/documents/doc_test/stat-blocks").json()
    assert index[0]["name"] == "Gobelin"
    detail = api_client.get("/documents/doc_test/stat-blocks/Gobelin").json()
    assert detail["nc"] == 1
    assert detail["attributes"]["FOR"] == "10"


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
