from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from rpg_assistant.ingestion.feedback.visual_review import (
    VISUAL_INGESTION_REVIEW_PROMPT,
    VisualReviewError,
    prepare_visual_ingestion_review as run_visual_review,
)
from rpg_assistant.ingestion.raw.importer import run as import_run
from rpg_assistant.ingestion.semantic.schemas import (
    CHUNK_CLASSIFICATION_JSON_SCHEMA,
    CHUNK_TYPES,
    ENTITY_EXTRACTION_PROMPT,
    ENTITY_JSON_SCHEMA,
    ENTITY_TYPES,
    RELATION_TYPES,
)
from rpg_assistant.ingestion.semantic.validator import (
    validate_semantic_layer as run_semantic_validation,
)
from rpg_assistant.models.semantic import (
    ChunkClassification,
    EntityRecord,
    EntityRelationRecord,
    EntitySourceRef,
)
from rpg_assistant.storage.db import get_connection
from rpg_assistant.storage.repositories.raw import RawRepository
from rpg_assistant.storage.repositories.semantic import SemanticRepository

mcp = FastMCP("rpg-assistant")


class ChunkClassificationInput(BaseModel):
    chunk_id: str
    chunk_type: str
    confidence: float = Field(ge=0.0, le=1.0)


class EntitySourceRefInput(BaseModel):
    document_id: str | None = None
    page: int
    chunk_id: str
    page_block_ids: list[str] = Field(default_factory=list)
    bbox: dict[str, float] | None = None
    evidence_excerpt: str | None = None


class EntityInput(BaseModel):
    entity_id: str
    type: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    summary: str = ""
    player_safe: dict[str, Any] = Field(default_factory=dict)
    gm_only: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[EntitySourceRefInput]
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelationInput(BaseModel):
    from_entity_id: str
    relation_type: str
    to_entity_id: str
    source_refs: list[EntitySourceRefInput] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _to_entity_source_ref(ref: EntitySourceRefInput) -> EntitySourceRef:
    bbox = None
    if ref.bbox:
        from rpg_assistant.models.raw import BBox

        bbox = BBox(**ref.bbox)
    return EntitySourceRef(
        document_id=ref.document_id,
        page=ref.page,
        chunk_id=ref.chunk_id,
        page_block_ids=ref.page_block_ids,
        bbox=bbox,
        evidence_excerpt=ref.evidence_excerpt,
    )


@mcp.tool()
def import_pdf(
    pdf_path: str,
    campaign_id: str,
    campaign_title: str = "",
    game_system: str = "",
) -> str:
    """Run Stage A raw extraction (same pipeline as rpg-ingest raw extract)."""
    result = import_run(
        Path(pdf_path),
        campaign_id=campaign_id,
        campaign_title=campaign_title,
        game_system=game_system,
    )
    return json.dumps(result.__dict__, indent=2, default=str)


@mcp.tool()
def get_ingestion_status(ingestion_run_id: str) -> str:
    """Return status and stats for an ingestion run."""
    with get_connection() as conn:
        repo = RawRepository(conn)
        run_record = repo.get_ingestion_run(ingestion_run_id)
    if not run_record:
        return json.dumps({"error": f"Unknown ingestion_run_id: {ingestion_run_id}"})
    return json.dumps(run_record.model_dump(), indent=2, default=str)


@mcp.tool()
def list_campaigns() -> str:
    """List all campaigns with title, game system, and document counts."""
    with get_connection() as conn:
        repo = RawRepository(conn)
        campaigns = repo.list_campaigns()
    return json.dumps([c.model_dump() for c in campaigns], indent=2, default=str)


@mcp.tool()
def list_documents(campaign_id: str) -> str:
    """List documents ingested for a campaign (sections, chunks, latest raw run)."""
    with get_connection() as conn:
        repo = RawRepository(conn)
        documents = repo.list_documents(campaign_id)
    return json.dumps([d.model_dump() for d in documents], indent=2, default=str)


@mcp.tool()
def list_sections(document_id: str) -> str:
    """List section tree for a document."""
    with get_connection() as conn:
        repo = RawRepository(conn)
        sections = repo.list_sections(document_id)
    return json.dumps([s.model_dump() for s in sections], indent=2)


@mcp.tool()
def list_chunks(
    document_id: str,
    section_id: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List chunks for a document with optional filters."""
    with get_connection() as conn:
        repo = RawRepository(conn)
        chunks = repo.list_chunks(
            document_id,
            section_id=section_id,
            page_start=page_start,
            page_end=page_end,
            limit=limit,
            offset=offset,
        )
    payload = [
        {
            "id": c.id,
            "section_id": c.section_id,
            "page_start": c.page_start,
            "page_end": c.page_end,
            "chunk_type": c.chunk_type,
            "chunk_type_hint": c.chunk_type_hint,
            "token_count": c.token_count,
            "needs_rechunk": c.needs_rechunk,
            "text_preview": c.text[:200],
        }
        for c in chunks
    ]
    return json.dumps(payload, indent=2)


@mcp.tool()
def get_chunk(chunk_id: str) -> str:
    """Return full chunk text, source spans, and metadata."""
    with get_connection() as conn:
        repo = RawRepository(conn)
        chunk = repo.get_chunk(chunk_id)
    if not chunk:
        return json.dumps({"error": f"Unknown chunk_id: {chunk_id}"})
    return json.dumps(chunk.model_dump(), indent=2)


@mcp.tool()
def prepare_visual_ingestion_review(
    document_id: str,
    pdf_path: str | None = None,
    section_count: int = 3,
    chunks_per_section: int = 2,
    seed: int | None = None,
    dpi: int = 150,
    max_pages: int = 15,
) -> str:
    """Sample random sections/chunks and render matching PDF pages for visual review."""
    try:
        with get_connection() as conn:
            repo = RawRepository(conn)
            payload = run_visual_review(
                repo,
                document_id,
                pdf_path=pdf_path,
                section_count=section_count,
                chunks_per_section=chunks_per_section,
                seed=seed,
                dpi=dpi,
                max_pages=max_pages,
            )
    except VisualReviewError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(payload, indent=2, default=str)


@mcp.tool()
def get_source_excerpt(page_block_ids: list[str]) -> str:
    """Return text and bounding boxes for page blocks (source verification)."""
    with get_connection() as conn:
        repo = RawRepository(conn)
        blocks = repo.get_page_blocks(page_block_ids)
    return json.dumps(
        [
            {
                "id": b.id,
                "page_number": b.page_number,
                "text": b.text,
                "bbox": b.bbox.model_dump(),
                "metadata": b.metadata,
            }
            for b in blocks
        ],
        indent=2,
    )


@mcp.tool()
def submit_chunk_classifications(
    ingestion_run_id: str,
    campaign_id: str,
    classifications: list[ChunkClassificationInput],
    submitted_by: str = "external_agent",
) -> str:
    """Submit agent-produced chunk classifications."""
    items = [
        ChunkClassification(
            chunk_id=c.chunk_id,
            chunk_type=c.chunk_type,
            confidence=c.confidence,
        )
        for c in classifications
    ]
    with get_connection() as conn:
        repo = SemanticRepository(conn)
        updated = repo.submit_chunk_classifications(
            ingestion_run_id=ingestion_run_id,
            campaign_id=campaign_id,
            submitted_by=submitted_by,
            classifications=items,
        )
    return json.dumps({"updated": updated, "submitted": len(items)}, indent=2)


@mcp.tool()
def submit_entities(
    ingestion_run_id: str,
    campaign_id: str,
    entities: list[EntityInput],
    submitted_by: str = "external_agent",
) -> str:
    """Submit extracted entities with mandatory source_refs."""
    records = [
        EntityRecord(
            entity_id=e.entity_id,
            type=e.type,
            name=e.name,
            aliases=e.aliases,
            summary=e.summary,
            player_safe=e.player_safe,
            gm_only=e.gm_only,
            source_refs=[_to_entity_source_ref(r) for r in e.source_refs],
            confidence=e.confidence,
            metadata=e.metadata,
        )
        for e in entities
    ]
    with get_connection() as conn:
        repo = SemanticRepository(conn)
        inserted = repo.submit_entities(
            ingestion_run_id=ingestion_run_id,
            campaign_id=campaign_id,
            submitted_by=submitted_by,
            entities=records,
        )
    return json.dumps({"entity_ids": inserted}, indent=2)


@mcp.tool()
def submit_relations(
    ingestion_run_id: str,
    campaign_id: str,
    relations: list[RelationInput],
    submitted_by: str = "external_agent",
) -> str:
    """Submit typed relations between known entities."""
    records = [
        EntityRelationRecord(
            from_entity_id=r.from_entity_id,
            relation_type=r.relation_type,
            to_entity_id=r.to_entity_id,
            source_refs=[_to_entity_source_ref(ref) for ref in r.source_refs],
            confidence=r.confidence,
            metadata=r.metadata,
        )
        for r in relations
    ]
    with get_connection() as conn:
        repo = SemanticRepository(conn)
        count = repo.submit_relations(
            ingestion_run_id=ingestion_run_id,
            campaign_id=campaign_id,
            submitted_by=submitted_by,
            relations=records,
        )
    return json.dumps({"submitted": count}, indent=2)


@mcp.tool()
def validate_semantic_layer(campaign_id: str) -> str:
    """Run deterministic validation on the semantic layer for a campaign."""
    with get_connection() as conn:
        result = run_semantic_validation(conn, campaign_id)
    return json.dumps(result.to_dict(), indent=2)


@mcp.tool()
def get_semantic_summary(campaign_id: str) -> str:
    """Summarize semantic enrichment state for a campaign."""
    with get_connection() as conn:
        repo = SemanticRepository(conn)
        summary = repo.get_semantic_summary(campaign_id)
    return json.dumps(summary, indent=2)


@mcp.resource("ingestion://schemas/entity")
def resource_entity_schema() -> str:
    return json.dumps(ENTITY_JSON_SCHEMA, indent=2)


@mcp.resource("ingestion://schemas/chunk_classification")
def resource_chunk_classification_schema() -> str:
    payload = {
        "schema": CHUNK_CLASSIFICATION_JSON_SCHEMA,
        "allowed_chunk_types": sorted(CHUNK_TYPES),
        "allowed_entity_types": sorted(ENTITY_TYPES),
        "allowed_relation_types": sorted(RELATION_TYPES),
    }
    return json.dumps(payload, indent=2)


@mcp.resource("ingestion://prompts/entity_extraction")
def resource_entity_extraction_prompt() -> str:
    return ENTITY_EXTRACTION_PROMPT


@mcp.resource("ingestion://prompts/visual_ingestion_review")
def resource_visual_ingestion_review_prompt() -> str:
    return VISUAL_INGESTION_REVIEW_PROMPT


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
