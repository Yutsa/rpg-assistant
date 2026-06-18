from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class SourceSpan(BaseModel):
    page: int
    page_block_ids: list[str] = Field(default_factory=list)
    bbox: BBox | None = None


class PageRecord(BaseModel):
    id: str
    document_id: str
    page_number: int
    text: str
    extraction_method: str = "pymupdf"
    has_text: bool = True
    text_coverage_ratio: float
    width: float | None = None
    height: float | None = None


class PageBlockRecord(BaseModel):
    id: str
    document_id: str
    page_id: str
    page_number: int
    block_index: int
    text: str
    bbox: BBox
    metadata: dict[str, Any] = Field(default_factory=dict)


class SectionRecord(BaseModel):
    id: str
    campaign_id: str
    document_id: str
    parent_section_id: str | None = None
    title: str
    level: int
    page_start: int
    page_end: int


class StatBlockIndexEntry(BaseModel):
    name: str
    nc: int | None = None
    chunk_id: str
    section_id: str | None = None
    uses_rulebook: bool = False
    pages: dict[str, int]


class ChunkRecord(BaseModel):
    id: str
    campaign_id: str
    document_id: str
    section_id: str | None = None
    page_start: int
    page_end: int
    text: str
    chunk_type: str | None = None
    chunk_type_hint: str | None = None
    token_count: int
    source_spans: list[SourceSpan] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    needs_rechunk: bool = False


class CampaignRecord(BaseModel):
    id: str
    title: str
    game_system: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    document_count: int = 0


class DocumentRecord(BaseModel):
    id: str
    campaign_id: str
    filename: str
    page_count: int = 0
    content_hash: str
    created_at: datetime | None = None
    section_count: int = 0
    chunk_count: int = 0
    latest_ingestion_run_id: str | None = None
    latest_ingestion_status: str | None = None


class IngestionRunRecord(BaseModel):
    id: str
    campaign_id: str
    document_id: str | None = None
    stage: str = "raw"
    status: str = "pending"
    error_message: str | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
