from __future__ import annotations

import sqlite3

from rpg_core.storage.db import _SqliteConnection
from rpg_core.storage.dialect import Dialect
from rpg_core.storage.repositories.raw import RawRepository

_BASE_SCHEMA = """
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

_PAGES_SCHEMA = """
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
"""

_SEMANTIC_SCHEMA = """
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


def memory_repo(
    *,
    with_pages: bool = False,
    with_semantic: bool = False,
    check_same_thread: bool = True,
) -> RawRepository:
    connection = sqlite3.connect(":memory:", check_same_thread=check_same_thread)
    connection.execute("PRAGMA foreign_keys = ON")
    schema = _BASE_SCHEMA
    if with_pages:
        schema += _PAGES_SCHEMA
    if with_semantic:
        schema += _SEMANTIC_SCHEMA
    connection.executescript(schema)
    return RawRepository(_SqliteConnection(connection, Dialect("sqlite")))
