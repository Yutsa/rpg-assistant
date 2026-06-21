-- Minimal raw tables for Clojure ingest tests (subset of Alembic 001 + 002)

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
    raw_layout_json TEXT,
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

CREATE INDEX idx_page_blocks_document_page
    ON page_blocks (document_id, page_number);

CREATE TABLE sections (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_section_id TEXT,
    title TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
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
