from __future__ import annotations

import sqlite3

from rpg_assistant.models.raw import IngestionRunRecord
from rpg_assistant.storage.db import _SqliteConnection
from rpg_assistant.storage.dialect import Dialect
from rpg_assistant.storage.repositories.raw import RawRepository


def _memory_repo() -> RawRepository:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    # Minimal tables for discovery queries
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
        """
    )
    return RawRepository(_SqliteConnection(connection, Dialect("sqlite")))


def test_list_campaigns_and_documents():
    repo = _memory_repo()
    repo.ensure_campaign("momie", title="Mondanités et Momie", game_system="D&D 5e")
    repo.upsert_document(
        "doc_1",
        campaign_id="momie",
        filename="momie.pdf",
        page_count=20,
        content_hash="abc",
    )
    repo.create_ingestion_run(
        IngestionRunRecord(
            id="run_1",
            campaign_id="momie",
            document_id="doc_1",
            stage="raw",
            status="completed",
        )
    )

    campaigns = repo.list_campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].id == "momie"
    assert campaigns[0].title == "Mondanités et Momie"
    assert campaigns[0].document_count == 1

    documents = repo.list_documents("momie")
    assert len(documents) == 1
    assert documents[0].id == "doc_1"
    assert documents[0].filename == "momie.pdf"
    assert documents[0].latest_ingestion_run_id == "run_1"
    assert documents[0].latest_ingestion_status == "completed"

    assert repo.list_documents("unknown") == []
