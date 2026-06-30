from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from rpg_core.models.raw import BBox, ChunkRecord, SourceSpan


class CampaignOut(BaseModel):
    id: str
    title: str
    game_system: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    document_count: int = 0


class DocumentOut(BaseModel):
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


class CampaignSummaryOut(BaseModel):
    campaign_id: str
    document_count: int
    section_count: int
    chunk_count: int
    chunks_total: int
    chunks_classified: int
    entities: int
    relations: int
    low_confidence_entities: int
    needs_review: int


class SectionOut(BaseModel):
    id: str
    campaign_id: str
    document_id: str
    parent_section_id: str | None = None
    title: str
    level: int
    page_start: int
    page_end: int


class ChunkListItem(BaseModel):
    id: str
    section_id: str | None = None
    page_start: int
    page_end: int
    chunk_type: str | None = None
    chunk_type_hint: str | None = None
    needs_rechunk: bool = False
    text_preview: str

    @classmethod
    def from_record(cls, chunk: ChunkRecord, *, preview_len: int = 200) -> ChunkListItem:
        from rpg_core.stat_blocks.serialize import chunk_to_list_item

        return cls(**chunk_to_list_item(chunk, preview_len=preview_len))


class ChunkOut(BaseModel):
    id: str
    campaign_id: str
    document_id: str
    section_id: str | None = None
    page_start: int
    page_end: int
    text: str
    chunk_type: str | None = None
    chunk_type_hint: str | None = None
    source_spans: list[SourceSpan] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    needs_rechunk: bool = False

    @classmethod
    def from_record(cls, chunk: ChunkRecord) -> ChunkOut:
        return cls(**chunk.model_dump())


class StatBlockIndexOut(BaseModel):
    name: str
    nc: int | str | None = None
    chunk_id: str
    section_id: str | None = None
    uses_rulebook: bool = False
    pages: dict[str, int]


class PageMetaOut(BaseModel):
    page_number: int
    width: float
    height: float


class PageBlockOut(BaseModel):
    id: str
    page_number: int
    block_index: int
    text: str
    bbox: BBox
    metadata: dict[str, Any] = Field(default_factory=dict)


class PageNodeOut(BaseModel):
    id: str
    depth: str
    node_type: str
    parent_id: str | None = None
    block_index: int
    line_index: int | None = None
    span_index: int | None = None
    text: str
    bbox: BBox
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractorPageOut(BaseModel):
    page_number: int
    width: float
    height: float
    extraction_method: str
    blocks: list[PageBlockOut]


class PageExtractorsCompareOut(BaseModel):
    page_number: int
    width: float
    height: float
    pymupdf: ExtractorPageOut
    pdfbox: ExtractorPageOut


class GameSystemOut(BaseModel):
    id: str
    label: str
    description: str = ""
    supports_stat_blocks: bool = False
    default: bool = False


class ImportCreateOut(BaseModel):
    ingestion_run_id: str
    campaign_id: str
    status: str


class IngestionRunOut(BaseModel):
    id: str
    campaign_id: str
    document_id: str | None = None
    status: str
    stage: str
    stats: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
