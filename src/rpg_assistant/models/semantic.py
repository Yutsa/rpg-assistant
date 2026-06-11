from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from rpg_assistant.models.raw import BBox


class EntitySourceRef(BaseModel):
    document_id: str | None = None
    page: int
    chunk_id: str
    page_block_ids: list[str] = Field(default_factory=list)
    bbox: BBox | None = None
    evidence_excerpt: str | None = None


class ChunkClassification(BaseModel):
    chunk_id: str
    chunk_type: str
    confidence: float = Field(ge=0.0, le=1.0)


class EntityRecord(BaseModel):
    entity_id: str
    type: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    summary: str = ""
    player_safe: dict[str, Any] = Field(default_factory=dict)
    gm_only: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[EntitySourceRef] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityRelationRecord(BaseModel):
    from_entity_id: str
    relation_type: str
    to_entity_id: str
    source_refs: list[EntitySourceRef] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    metadata: dict[str, Any] = Field(default_factory=dict)
