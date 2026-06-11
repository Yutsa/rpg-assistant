from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from rpg_assistant.models.raw import BBox, DocumentRecord
from rpg_assistant.models.semantic import EntityRecord, EntityRelationRecord


class ChunkListItem(BaseModel):
    id: str
    section_id: str | None = None
    page_start: int
    page_end: int
    chunk_type: str | None = None
    chunk_type_hint: str | None = None
    token_count: int
    needs_rechunk: bool = False
    text_preview: str


class EntityIndexEntry(BaseModel):
    entity_id: str
    type: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    summary: str = ""
    confidence: float = 0.5


class EntityRelationsResponse(BaseModel):
    outgoing: list[EntityRelationRecord] = Field(default_factory=list)
    incoming: list[EntityRelationRecord] = Field(default_factory=list)


class CampaignDocumentSummary(BaseModel):
    id: str
    filename: str
    page_count: int = 0
    section_count: int = 0
    chunk_count: int = 0
    latest_ingestion_run_id: str | None = None
    latest_ingestion_status: str | None = None


class CampaignSummary(BaseModel):
    campaign_id: str
    chunks_total: int = 0
    chunks_classified: int = 0
    entities: int = 0
    relations: int = 0
    low_confidence_entities: int = 0
    needs_review: int = 0
    documents: list[CampaignDocumentSummary] = Field(default_factory=list)


class PageBlockItem(BaseModel):
    id: str
    page_number: int
    block_index: int
    text: str
    bbox: BBox
    metadata: dict[str, Any] = Field(default_factory=dict)


def chunk_to_list_item(chunk: Any) -> ChunkListItem:
    return ChunkListItem(
        id=chunk.id,
        section_id=chunk.section_id,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        chunk_type=chunk.chunk_type,
        chunk_type_hint=chunk.chunk_type_hint,
        token_count=chunk.token_count,
        needs_rechunk=chunk.needs_rechunk,
        text_preview=chunk.text[:200],
    )


def entity_to_index_entry(entity: EntityRecord) -> EntityIndexEntry:
    return EntityIndexEntry(
        entity_id=entity.entity_id,
        type=entity.type,
        name=entity.name,
        aliases=entity.aliases,
        summary=entity.summary,
        confidence=entity.confidence,
    )


def document_to_summary(doc: DocumentRecord) -> CampaignDocumentSummary:
    return CampaignDocumentSummary(
        id=doc.id,
        filename=doc.filename,
        page_count=doc.page_count,
        section_count=doc.section_count,
        chunk_count=doc.chunk_count,
        latest_ingestion_run_id=doc.latest_ingestion_run_id,
        latest_ingestion_status=doc.latest_ingestion_status,
    )
