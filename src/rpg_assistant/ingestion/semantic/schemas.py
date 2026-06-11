from __future__ import annotations

CHUNK_TYPES = frozenset(
    {
        "location",
        "npc",
        "faction",
        "scene",
        "encounter",
        "clue",
        "secret",
        "item",
        "handout",
        "map",
        "stat_block",
        "lore",
        "rule",
        "table",
        "other",
    }
)

ENTITY_TYPES = frozenset(
    {
        "location",
        "npc",
        "faction",
        "scene",
        "encounter",
        "secret",
        "clue",
        "item",
        "monster",
        "organization",
        "timeline_event",
        "handout",
        "rule_reference",
    }
)

RELATION_TYPES = frozenset(
    {
        "located_in",
        "contains",
        "knows_secret",
        "reveals",
        "points_to",
        "requires",
        "unlocks",
        "opposes",
        "serves",
        "member_of",
        "appears_in",
        "connected_to",
        "caused_by",
        "threatens",
    }
)

GM_ONLY_KEYWORDS = (
    "secret",
    "gm only",
    "gm-only",
    "hidden truth",
    "behind the scenes",
    "actually",
    "in truth",
    "cult leader",
    "true identity",
)

ENTITY_JSON_SCHEMA = {
    "type": "object",
    "required": ["entity_id", "type", "name", "source_refs", "confidence"],
    "properties": {
        "entity_id": {"type": "string"},
        "type": {"type": "string", "enum": sorted(ENTITY_TYPES)},
        "name": {"type": "string"},
        "aliases": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "player_safe": {"type": "object"},
        "gm_only": {"type": "object"},
        "source_refs": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["page", "chunk_id"],
                "properties": {
                    "document_id": {"type": "string"},
                    "page": {"type": "integer"},
                    "chunk_id": {"type": "string"},
                    "page_block_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "bbox": {
                        "type": "object",
                        "properties": {
                            "x0": {"type": "number"},
                            "y0": {"type": "number"},
                            "x1": {"type": "number"},
                            "y1": {"type": "number"},
                        },
                    },
                    "evidence_excerpt": {"type": "string"},
                },
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

CHUNK_CLASSIFICATION_JSON_SCHEMA = {
    "type": "object",
    "required": ["chunk_id", "chunk_type", "confidence"],
    "properties": {
        "chunk_id": {"type": "string"},
        "chunk_type": {"type": "string", "enum": sorted(CHUNK_TYPES)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

ENTITY_EXTRACTION_PROMPT = """You are extracting structured RPG campaign facts from source chunks.

Rules:
- Every entity MUST include at least one source_ref with an existing chunk_id.
- Separate player_safe (spoiler-free) from gm_only (secrets, motivations, hidden truths).
- Use only allowed entity types and relation types from the ingestion schemas.
- Do not invent facts not supported by the chunk text.
- Include confidence between 0 and 1.

Workflow:
1. Read chunks via get_chunk.
2. Classify chunks via submit_chunk_classifications.
3. Submit entities with source_refs via submit_entities.
4. Submit relations between known entities via submit_relations.
5. Run validate_semantic_layer and fix reported issues.
"""
