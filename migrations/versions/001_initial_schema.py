"""Initial raw and semantic tables.

Revision ID: 001
Revises:
Create Date: 2026-06-10

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _postgres_schema() -> str:
    return """
        CREATE TABLE campaigns (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            game_system TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            page_count INTEGER NOT NULL DEFAULT 0,
            content_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE ingestion_runs (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
            stage TEXT NOT NULL DEFAULT 'raw',
            status TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT,
            stats JSONB NOT NULL DEFAULT '{}'::jsonb,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ
        );

        CREATE TABLE pages (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            page_number INTEGER NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            extraction_method TEXT NOT NULL DEFAULT 'pymupdf',
            has_text BOOLEAN NOT NULL DEFAULT TRUE,
            text_coverage_ratio DOUBLE PRECISION NOT NULL DEFAULT 0,
            width DOUBLE PRECISION,
            height DOUBLE PRECISION,
            UNIQUE (document_id, page_number)
        );

        CREATE TABLE page_blocks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            page_id TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
            page_number INTEGER NOT NULL,
            block_index INTEGER NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            bbox_json JSONB NOT NULL,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
        );

        CREATE INDEX idx_page_blocks_document_page
            ON page_blocks (document_id, page_number);

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
            source_spans_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            needs_rechunk BOOLEAN NOT NULL DEFAULT FALSE
        );

        CREATE INDEX idx_chunks_document ON chunks (document_id);
        CREATE INDEX idx_chunks_campaign ON chunks (campaign_id);

        CREATE TABLE entities (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            aliases_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            summary TEXT NOT NULL DEFAULT '',
            player_safe_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            gm_only_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
            ingestion_run_id TEXT,
            submitted_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE entity_source_refs (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
            chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
            page_number INTEGER NOT NULL,
            evidence_excerpt TEXT,
            page_block_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            bbox_json JSONB
        );

        CREATE TABLE entity_relations (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            from_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            relation_type TEXT NOT NULL,
            to_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            source_refs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            ingestion_run_id TEXT,
            submitted_by TEXT
        );

        CREATE TABLE extraction_reviews (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            ingestion_run_id TEXT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            reviewer_model TEXT,
            review_prompt_version TEXT,
            verdict TEXT,
            issues_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            missing_information_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            confidence_adjustment DOUBLE PRECISION,
            source_refs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE correction_attempts (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            ingestion_run_id TEXT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            review_id TEXT REFERENCES extraction_reviews(id) ON DELETE SET NULL,
            original_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            corrected_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            correction_model TEXT,
            correction_prompt_version TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """


def _sqlite_schema() -> str:
    return """
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

        CREATE INDEX idx_page_blocks_document_page
            ON page_blocks (document_id, page_number);

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

        CREATE INDEX idx_chunks_document ON chunks (document_id);
        CREATE INDEX idx_chunks_campaign ON chunks (campaign_id);

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

        CREATE TABLE extraction_reviews (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            ingestion_run_id TEXT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            reviewer_model TEXT,
            review_prompt_version TEXT,
            verdict TEXT,
            issues_json TEXT NOT NULL DEFAULT '[]',
            missing_information_json TEXT NOT NULL DEFAULT '[]',
            confidence_adjustment REAL,
            source_refs_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE correction_attempts (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            ingestion_run_id TEXT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            review_id TEXT REFERENCES extraction_reviews(id) ON DELETE SET NULL,
            original_payload_json TEXT NOT NULL DEFAULT '{}',
            corrected_payload_json TEXT NOT NULL DEFAULT '{}',
            correction_model TEXT,
            correction_prompt_version TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """


def upgrade() -> None:
    bind = op.get_bind()
    schema = _sqlite_schema() if bind.dialect.name == "sqlite" else _postgres_schema()
    for statement in schema.split(";"):
        sql = statement.strip()
        if sql:
            op.execute(text(sql))


def downgrade() -> None:
    for table in (
        "correction_attempts",
        "extraction_reviews",
        "entity_relations",
        "entity_source_refs",
        "entities",
        "chunks",
        "sections",
        "page_blocks",
        "pages",
        "ingestion_runs",
        "documents",
        "campaigns",
    ):
        op.execute(text(f"DROP TABLE IF EXISTS {table}"))
