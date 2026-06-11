from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from rpg_assistant.api.deps import get_db
from rpg_assistant.api.main import create_app
from rpg_assistant.models.raw import (
    BBox,
    ChunkRecord,
    PageBlockRecord,
    PageRecord,
    SectionRecord,
    SourceSpan,
)
from rpg_assistant.models.semantic import EntityRecord, EntityRelationRecord, EntitySourceRef
from rpg_assistant.storage.db import _SqliteConnection
from rpg_assistant.storage.dialect import Dialect
from rpg_assistant.storage.repositories.raw import RawRepository
from rpg_assistant.storage.repositories.semantic import SemanticRepository

_MEMORY_SCHEMA = """
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
    text_coverage_ratio REAL NOT NULL DEFAULT 0,
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
    bbox_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_page_blocks_document_page ON page_blocks (document_id, page_number);
CREATE TABLE sections (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_section_id TEXT REFERENCES sections(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL
);
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_id TEXT REFERENCES sections(id) ON DELETE SET NULL,
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
    submitted_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE entity_source_refs (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
    chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    evidence_excerpt TEXT,
    page_block_ids_json TEXT NOT NULL DEFAULT '[]',
    bbox_json TEXT
);
CREATE TABLE entity_relations (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    from_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    to_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    source_refs_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0.5,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    ingestion_run_id TEXT,
    submitted_by TEXT
);
"""


def _memory_connection() -> _SqliteConnection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(_MEMORY_SCHEMA)
    return _SqliteConnection(connection, Dialect("sqlite"))


def _azulria_metadata() -> dict:
    return {
        "stat_block": {
            "name": "AZULRIA",
            "subtitle": "PRÊTRESSE 7",
            "nc": 4,
            "attributes": {"AGI": 1, "FOR": 3},
            "abilities": [{"title": "PASSAGE DANS LA PIERRE", "text": "Deux fois par jour."}],
            "raw_text": "AZULRIA | NC 4",
            "block_refs": [],
            "game_system": "cof2",
        },
        "game_system": "cof2",
    }


def _make_test_pdf(path: Path, pages: list[str]) -> None:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text)
    document.save(path)
    document.close()


@pytest.fixture
def db_conn() -> Generator[_SqliteConnection, None, None]:
    yield _memory_connection()


@pytest.fixture
def client(db_conn: _SqliteConnection) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Generator[_SqliteConnection, None, None]:
        yield db_conn

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed_campaign(repo: RawRepository, campaign_id: str = "momie") -> None:
    repo.ensure_campaign(campaign_id, title="Test Campaign", game_system="cof2")
    repo.conn.commit()


def _seed_document(
    repo: RawRepository,
    document_id: str = "doc_test",
    campaign_id: str = "momie",
) -> None:
    repo.upsert_document(document_id, campaign_id, "test.pdf", 2, "hash123")
    repo.conn.commit()


def _insert_chunk(
    repo: RawRepository,
    chunk_id: str,
    *,
    section_id: str | None = None,
    page_start: int = 1,
    page_end: int = 1,
    text: str = "chunk text",
    chunk_type: str | None = None,
    chunk_type_hint: str | None = None,
    metadata: dict | None = None,
) -> None:
    repo.insert_chunks(
        [
            ChunkRecord(
                id=chunk_id,
                campaign_id="momie",
                document_id="doc_test",
                section_id=section_id,
                page_start=page_start,
                page_end=page_end,
                text=text,
                chunk_type=chunk_type,
                chunk_type_hint=chunk_type_hint,
                token_count=len(text.split()),
                source_spans=[SourceSpan(page=page_start, page_block_ids=["pb_1"])],
                metadata=metadata or {},
            )
        ]
    )
    repo.conn.commit()


def _insert_stat_chunk(
    repo: RawRepository,
    chunk_id: str,
    metadata: dict,
    *,
    page_start: int = 15,
    page_end: int = 15,
) -> None:
    _insert_chunk(
        repo,
        chunk_id,
        page_start=page_start,
        page_end=page_end,
        text="stat text",
        chunk_type_hint="stat_block",
        metadata=metadata,
    )


class TestCampaigns:
    def test_list_campaigns_empty(self, client: TestClient) -> None:
        response = client.get("/campaigns")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_campaigns_populated(self, client: TestClient, db_conn: _SqliteConnection) -> None:
        repo = RawRepository(db_conn)
        _seed_campaign(repo)
        _seed_document(repo)

        response = client.get("/campaigns")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "momie"
        assert data[0]["document_count"] == 1

    def test_list_documents_unknown_campaign(self, client: TestClient) -> None:
        response = client.get("/campaigns/unknown/documents")
        assert response.status_code == 404

    def test_campaign_summary(self, client: TestClient, db_conn: _SqliteConnection) -> None:
        raw_repo = RawRepository(db_conn)
        sem_repo = SemanticRepository(db_conn)
        _seed_campaign(raw_repo)
        _seed_document(raw_repo)
        _insert_chunk(raw_repo, "chk_1", chunk_type="narration", text="a" * 250)
        sem_repo.submit_entities(
            ingestion_run_id="run_sem",
            campaign_id="momie",
            submitted_by="test",
            entities=[
                EntityRecord(
                    entity_id="ent_hero",
                    type="character",
                    name="Hero",
                    summary="A hero",
                    source_refs=[
                        EntitySourceRef(
                            document_id="doc_test",
                            page=1,
                            chunk_id="chk_1",
                        )
                    ],
                    confidence=0.9,
                )
            ],
        )
        db_conn.commit()

        response = client.get("/campaigns/momie/summary")
        assert response.status_code == 200
        summary = response.json()
        assert summary["campaign_id"] == "momie"
        assert summary["chunks_total"] == 1
        assert summary["entities"] == 1
        assert len(summary["documents"]) == 1
        assert summary["documents"][0]["chunk_count"] == 1


class TestChunks:
    def test_list_chunks_preview_and_filters(
        self, client: TestClient, db_conn: _SqliteConnection
    ) -> None:
        repo = RawRepository(db_conn)
        _seed_campaign(repo)
        _seed_document(repo)
        _insert_chunk(repo, "chk_p1", page_start=1, page_end=1, text="x" * 250)
        _insert_chunk(repo, "chk_p2", page_start=2, page_end=2, text="page two")
        repo.insert_sections(
            [
                SectionRecord(
                    id="sec_1",
                    campaign_id="momie",
                    document_id="doc_test",
                    title="Intro",
                    level=1,
                    page_start=1,
                    page_end=1,
                )
            ]
        )
        repo.conn.commit()
        _insert_chunk(
            repo,
            "chk_sec",
            section_id="sec_1",
            page_start=1,
            page_end=1,
            text="section chunk",
        )

        response = client.get("/documents/doc_test/chunks")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 3
        previews = {item["id"]: item["text_preview"] for item in items}
        assert len(previews["chk_p1"]) == 200

        filtered = client.get(
            "/documents/doc_test/chunks",
            params={"page_start": 2, "page_end": 2, "limit": 10, "offset": 0},
        )
        assert filtered.status_code == 200
        assert [c["id"] for c in filtered.json()] == ["chk_p2"]

        by_section = client.get(
            "/documents/doc_test/chunks",
            params={"section_id": "sec_1"},
        )
        assert by_section.status_code == 200
        assert [c["id"] for c in by_section.json()] == ["chk_sec"]

    def test_get_chunk_not_found(self, client: TestClient) -> None:
        response = client.get("/chunks/missing")
        assert response.status_code == 404


class TestStatBlocks:
    def test_stat_block_not_found(self, client: TestClient, db_conn: _SqliteConnection) -> None:
        repo = RawRepository(db_conn)
        _seed_campaign(repo)
        _seed_document(repo)

        response = client.get("/documents/doc_test/stat-blocks/UNKNOWN")
        assert response.status_code == 404

    def test_stat_block_ambiguous(self, client: TestClient, db_conn: _SqliteConnection) -> None:
        repo = RawRepository(db_conn)
        _seed_campaign(repo)
        _seed_document(repo)
        _insert_stat_chunk(repo, "chk_a", _azulria_metadata(), page_start=15)
        _insert_stat_chunk(repo, "chk_b", _azulria_metadata(), page_start=16)

        response = client.get("/documents/doc_test/stat-blocks/azulria")
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["error"] == "Ambiguous stat block"
        assert len(detail["candidates"]) == 2

    def test_stat_block_found(self, client: TestClient, db_conn: _SqliteConnection) -> None:
        repo = RawRepository(db_conn)
        _seed_campaign(repo)
        _seed_document(repo)
        _insert_stat_chunk(repo, "chk_azulria", _azulria_metadata())

        response = client.get("/documents/doc_test/stat-blocks/AZULRIA")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "AZULRIA"
        assert data["chunk_id"] == "chk_azulria"


class TestEntities:
    def test_entities_and_relations(self, client: TestClient, db_conn: _SqliteConnection) -> None:
        raw_repo = RawRepository(db_conn)
        sem_repo = SemanticRepository(db_conn)
        _seed_campaign(raw_repo)
        _seed_document(raw_repo)
        _insert_chunk(raw_repo, "chk_1")
        sem_repo.submit_entities(
            ingestion_run_id="run_sem",
            campaign_id="momie",
            submitted_by="test",
            entities=[
                EntityRecord(
                    entity_id="ent_a",
                    type="location",
                    name="Temple",
                    summary="Ancient temple",
                    source_refs=[
                        EntitySourceRef(
                            document_id="doc_test",
                            page=1,
                            chunk_id="chk_1",
                            evidence_excerpt="temple ruins",
                        )
                    ],
                    confidence=0.8,
                ),
                EntityRecord(
                    entity_id="ent_b",
                    type="character",
                    name="Guard",
                    summary="A guard",
                    source_refs=[
                        EntitySourceRef(
                            document_id="doc_test",
                            page=1,
                            chunk_id="chk_1",
                        )
                    ],
                    confidence=0.7,
                ),
            ],
        )
        sem_repo.submit_relations(
            ingestion_run_id="run_sem",
            campaign_id="momie",
            submitted_by="test",
            relations=[
                EntityRelationRecord(
                    from_entity_id="ent_b",
                    relation_type="located_in",
                    to_entity_id="ent_a",
                    source_refs=[],
                    confidence=0.6,
                )
            ],
        )
        db_conn.commit()

        list_response = client.get("/campaigns/momie/entities")
        assert list_response.status_code == 200
        entities = list_response.json()
        assert len(entities) == 2
        assert "source_refs" not in entities[0]

        typed = client.get("/campaigns/momie/entities", params={"type": "location"})
        assert typed.status_code == 200
        assert len(typed.json()) == 1
        assert typed.json()[0]["name"] == "Temple"

        detail = client.get("/entities/ent_a")
        assert detail.status_code == 200
        entity = detail.json()
        assert entity["name"] == "Temple"
        assert len(entity["source_refs"]) == 1
        assert entity["source_refs"][0]["evidence_excerpt"] == "temple ruins"

        relations = client.get("/entities/ent_b/relations")
        assert relations.status_code == 200
        rel_data = relations.json()
        assert len(rel_data["outgoing"]) == 1
        assert rel_data["outgoing"][0]["relation_type"] == "located_in"
        assert len(rel_data["incoming"]) == 0

        incoming = client.get("/entities/ent_a/relations")
        assert incoming.status_code == 200
        assert len(incoming.json()["incoming"]) == 1


class TestPages:
    def test_page_render(
        self, client: TestClient, db_conn: _SqliteConnection, tmp_path: Path
    ) -> None:
        raw_repo = RawRepository(db_conn)
        _seed_campaign(raw_repo)
        _seed_document(raw_repo)

        pdf_path = tmp_path / "sample.pdf"
        _make_test_pdf(pdf_path, ["Page one text", "Page two text"])

        response = client.get(
            "/documents/doc_test/pages/1/render",
            params={"pdf_path": str(pdf_path), "dpi": 72},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert len(response.content) > 0

    def test_page_blocks_bbox(self, client: TestClient, db_conn: _SqliteConnection) -> None:
        raw_repo = RawRepository(db_conn)
        _seed_campaign(raw_repo)
        _seed_document(raw_repo)
        raw_repo.insert_pages(
            [
                PageRecord(
                    id="page_1",
                    document_id="doc_test",
                    page_number=1,
                    text="Hello world",
                    text_coverage_ratio=0.5,
                )
            ]
        )
        raw_repo.insert_page_blocks(
            [
                PageBlockRecord(
                    id="pb_1",
                    document_id="doc_test",
                    page_id="page_1",
                    page_number=1,
                    block_index=0,
                    text="Hello",
                    bbox=BBox(x0=10.0, y0=20.0, x1=100.0, y1=40.0),
                ),
                PageBlockRecord(
                    id="pb_2",
                    document_id="doc_test",
                    page_id="page_1",
                    page_number=1,
                    block_index=1,
                    text="world",
                    bbox=BBox(x0=10.0, y0=50.0, x1=80.0, y1=70.0),
                ),
            ]
        )
        db_conn.commit()

        response = client.get("/documents/doc_test/pages/1/blocks")
        assert response.status_code == 200
        blocks = response.json()
        assert len(blocks) == 2
        assert blocks[0]["bbox"] == {"x0": 10.0, "y0": 20.0, "x1": 100.0, "y1": 40.0}
        assert blocks[0]["block_index"] == 0
        assert blocks[1]["text"] == "world"
