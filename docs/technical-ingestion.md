# Technical Ingestion Notes

## Goal

The ingestion system transforms a campaign PDF into a structured, source-backed, spoiler-aware campaign database.

The output should be usable by two consumers:

- An HTTP API for programmatic access and external tools.
- A retrieval layer for an AI GM.

The goal is not to store a large PDF and chat over it. The goal is to create a playable representation of the campaign: entities, relationships, secrets, clues, scenes, source references, and runtime-ready context packets.

## Core Principle

Use deterministic code for mechanical work and LLMs for semantic interpretation.

Code should handle:

- PDF text extraction.
- Rejection of scanned or image-only PDFs.
- Page and source reference tracking.
- Text position extraction for source highlighting.
- Heading and section detection.
- Chunk creation.
- Storage.
- Schema validation.
- Embedding generation.
- Deterministic checks.

LLMs should handle:

- Semantic classification.
- Entity extraction.
- Secret and clue extraction.
- Player-safe vs GM-only separation.
- Relationship extraction.
- Reveal condition inference.
- Ambiguous entity resolution.
- Summaries and scene packet generation.

The ingestion process should be a controlled pipeline, not a free-form autonomous agent.

## Proposed Pipeline

### 1. Document Import

Input:

- PDF file.
- Campaign metadata if known.
- Game system metadata if known.

Output:

- Document record.
- Page records.
- Extracted raw text.
- Text blocks with layout coordinates.
- Import rejection if the document has no usable text layer.

Important fields:

```json
{
  "document_id": "doc_anathazerin",
  "campaign_id": "camp_anathazerin",
  "page_number": 42,
  "text": "...",
  "extraction_method": "pymupdf",
  "has_text": true,
  "text_coverage_ratio": 0.94
}
```

If text extraction returns little or no text, reject the document as unsupported. Scanned and image-only PDFs are intentionally out of scope for the first version. The importer should explain that a text-based PDF is required.

### 1.1 Source Layout Extraction

For source verification, extraction should preserve text positions in addition to plain text.

With a library such as PyMuPDF, use structured extraction rather than only plain text extraction. The ingestion process should store page blocks, lines, and spans with bounding boxes when available.

Example page block:

```json
{
  "page_block_id": "block_073_004",
  "document_id": "doc_anathazerin",
  "page_number": 73,
  "block_index": 4,
  "text": "Mira refuses to speak unless shown the amulet...",
  "bbox": {
    "x0": 64.2,
    "y0": 188.4,
    "x1": 512.8,
    "y1": 244.1
  }
}
```

Clients (API, MCP tools) can use these coordinates to open the original PDF at the correct page and draw a highlight over the source region.

#### Extraction providers (`docling` / `legacy`)

The raw pipeline supports two backends, selected via CLI `--extraction-provider` or env `RPG_EXTRACTION_PROVIDER` (default: `docling`):

| Provider | Engine | Sections / chunks | Fallback |
|----------|--------|-------------------|----------|
| `docling` | IBM Docling (layout AI + reading order) | Heading levels from Docling; chunks by logical order | Auto-fallback to `legacy` on conversion error |
| `legacy` | PyMuPDF block extraction | Font/column heuristics (`sections.py`, `chunking.py`) | — |

Docling path: `DoclingDocument` → internal `DocElement` list → `LayoutPage` blocks → COF2/stat-block post-processing (unchanged) → `detect_sections_from_elements` / `build_chunks_from_elements`.

**Costs and operational notes (Docling):**

- Heavy Python dependencies: PyTorch, transformers, layout/table models (~hundreds of MB disk).
- First run downloads models from Hugging Face / ModelScope (network, cache under `~/.cache`).
- CPU-only by default; GPU speeds layout inference when available.
- `do_ocr=False` by default (text-native PDFs). Enable OCR only for scanned documents — pulls RapidOCR models and is significantly slower.
- Docling is MIT-licensed; bundled OCR backends (RapidOCR/Paddle) have separate licenses.
- Multi-column RPG layouts may be merged by Docling; use `legacy` or visual review when precision matters.

### 2. Document Structure Detection

Detect the campaign's structure:

- Front matter.
- Table of contents.
- Chapters.
- Sections.
- Subsections.
- Appendices.
- Handouts.
- Bestiary/stat blocks.
- Maps.

This should start with deterministic layout and heading heuristics. LLM assistance can be used when the structure is ambiguous.

Output example:

```json
{
  "section_id": "sec_chapter_03_tower",
  "title": "The Black Tower",
  "level": 2,
  "page_start": 41,
  "page_end": 58,
  "parent_section_id": "sec_chapter_03"
}
```

### 3. Chunking

Create source chunks for retrieval and extraction.

Chunking should preserve campaign structure where possible. Avoid only using arbitrary fixed-size chunks.

Useful chunk types:

- Chapter overview.
- Scene.
- Location.
- Room.
- NPC description.
- Encounter.
- Stat block.
- Clue.
- Secret.
- Handout.
- Table.
- Lore/sidebar.
- Rule reference.

Each chunk should include source references:

```json
{
  "chunk_id": "chunk_042_003",
  "campaign_id": "camp_anathazerin",
  "document_id": "doc_anathazerin",
  "page_start": 42,
  "page_end": 43,
  "section_id": "sec_chapter_03_tower",
  "text": "...",
  "estimated_tokens": 850,
  "chunk_type_hint": "location",
  "source_spans": [
    {
      "page": 42,
      "page_block_ids": ["block_042_006", "block_042_007"],
      "bbox": {
        "x0": 58.0,
        "y0": 140.0,
        "x1": 520.0,
        "y1": 380.0
      }
    }
  ]
}
```

### 4. Chunk Classification

Classify each chunk using a small model where possible.

Possible labels:

```text
location
npc
faction
scene
encounter
clue
secret
item
handout
map
stat_block
lore
rule
table
other
```

The classifier can output multiple labels with confidence scores.

### 5. Entity Extraction

Extract candidate entities from chunks.

Entity types:

- Location.
- NPC.
- Faction.
- Scene.
- Encounter.
- Secret.
- Clue.
- Item.
- Monster.
- Organization.
- Timeline event.
- Handout.
- Rule reference.

Every extracted entity must include:

- Type.
- Name.
- Short summary.
- Source references.
- Confidence score.
- Player-safe fields.
- GM-only fields when relevant.

Example:

```json
{
  "entity_id": "npc_mira",
  "type": "npc",
  "name": "Mira",
  "aliases": ["Mira the Innkeeper"],
  "summary": "The innkeeper who knows more about the disappearances than she admits.",
  "player_safe": {
    "description": "A tired innkeeper who avoids speaking about the old ruins."
  },
  "gm_only": {
    "secrets": ["Mira has seen the cult symbol before."],
    "motivation": "She wants to protect her brother."
  },
  "source_refs": [
    {
      "document_id": "doc_anathazerin",
      "page": 73,
      "chunk_id": "chunk_073_002",
      "page_block_ids": ["block_073_004"],
      "bbox": {
        "x0": 64.2,
        "y0": 188.4,
        "x1": 512.8,
        "y1": 244.1
      }
    }
  ],
  "confidence": 0.86
}
```

### 6. Relation Extraction

Extract typed relationships between entities.

Useful relation types:

```text
located_in
contains
knows_secret
reveals
points_to
requires
unlocks
opposes
serves
member_of
appears_in
connected_to
caused_by
threatens
```

Example:

```json
{
  "from_entity_id": "clue_bloody_symbol",
  "relation_type": "reveals",
  "to_entity_id": "secret_cult_under_temple",
  "source_refs": [
    {
      "page": 81,
      "chunk_id": "chunk_081_004"
    }
  ],
  "confidence": 0.78
}
```

Relations should be source-backed. Low-confidence relations should go to a review queue.

### 7. Spoiler and Reveal Modeling

This is critical for both human-facing tools and the AI GM.

Separate:

- Player-visible descriptions.
- GM-only truths.
- Hidden secrets.
- Reveal conditions.
- Already revealed state.

Example:

```json
{
  "secret_id": "secret_cult_under_temple",
  "truth": "The old temple cellar is used by the cult.",
  "safe_teaser": "Something about the temple feels deliberately concealed.",
  "reveal_conditions": [
    {
      "type": "location_search",
      "location_id": "loc_old_temple_cellar"
    },
    {
      "type": "npc_interaction",
      "npc_id": "npc_mira",
      "condition": "Mira is shown the amulet."
    }
  ],
  "source_refs": [
    {
      "page": 84,
      "chunk_id": "chunk_084_001"
    }
  ]
}
```

The AI GM should never receive all secrets by default. It should receive only the secrets relevant to the current scene, along with explicit reveal rules.

### 8. Entity Resolution and Deduplication

Campaign books often refer to the same thing in many ways.

Examples:

- "Lord Armand", "Armand", "the baron".
- "The old temple", "ruined shrine", "temple of the forgotten god".
- "The Black Tower", "tower ruins", "cult tower".

Use deterministic normalization first:

- Case folding.
- Alias lists.
- Section proximity.
- Exact and fuzzy string matching.

Use an LLM for ambiguous cases.

Store merge decisions explicitly:

```json
{
  "canonical_entity_id": "npc_lord_armand",
  "merged_entity_ids": ["npc_armand", "npc_the_baron"],
  "reason": "Same title, location, and role across chapter 2.",
  "confidence": 0.91,
  "reviewed_by_human": false
}
```

### 9. Adversarial Evidence Review

Before final validation, extracted data should go through an adversarial evidence review step.

This should not be a free-form autonomous agent. It should be a constrained reviewer whose job is to challenge the extracted data against the source text.

The reviewer receives:

- The original source chunk or source spans.
- The extracted candidate entity, relation, secret, or scene packet.
- The relevant schema.
- The source references claimed by the extractor.
- The current confidence score.

The reviewer should look for:

- Unsupported claims.
- Contradictions with the source.
- Overconfident inference.
- Missing conditions.
- Spoilers in player-safe fields.
- Relations that are plausible but not actually supported.
- Incorrect entity merges.
- Important facts omitted from the extraction.

Example review output:

```json
{
  "review_id": "review_000123",
  "target_type": "entity",
  "target_id": "npc_mira",
  "verdict": "needs_revision",
  "issues": [
    {
      "type": "unsupported_claim",
      "severity": "high",
      "field": "gm_only.secrets[0]",
      "reason": "The source says Mira is afraid of the symbol, but does not establish that she knows the cult leader.",
      "suggested_fix": "Replace this secret with a weaker claim or lower confidence."
    }
  ],
  "missing_information": [],
  "confidence_adjustment": -0.25
}
```

Recommended verdicts:

```text
pass
needs_revision
human_review
```

Avoid allowing the reviewer to rewrite the canonical extraction directly. The reviewer should produce objections and suggested fixes. A correction pass can then revise the extraction using the original source and the review output.

Recommended loop:

```text
extract candidate
schema validation
adversarial evidence review
single correction pass if needed
final validation
human review if still uncertain
```

The loop should be bounded. Do not allow endless extractor/reviewer debate during automated ingestion.

### 10. Final Validation and Review

The ingestion output should be validated before being used by the GM Agent.

Validation checks:

- Every entity has source references.
- Every relation references known entities.
- Every secret has at least one source reference.
- Every clue reveals or points to something, or is marked as atmospheric.
- Scene packets do not include unrelated secrets.
- Player-safe text does not contain obvious GM-only facts.
- Low-confidence extraction is flagged.
- Adversarial reviews are resolved or explicitly marked for human review.

Manual review should be supported from the start, even if the interface is basic.

## Data Storage Recommendation

Start with:

```text
PostgreSQL + JSONB + pgvector
```

Why:

- SQL handles campaigns, documents, chunks, entities, and relations cleanly.
- JSONB supports variable game-system-specific fields.
- pgvector supports semantic search without adding a separate vector database.
- PostgreSQL keeps operational complexity low.

Avoid starting with too many databases unless required.

Neo4j or another graph database may become useful later if graph exploration becomes a primary feature. MongoDB can work for flexible documents, but the project will likely need strong relationships and traceability, which makes PostgreSQL a better default.

## Suggested Tables

### campaigns

```text
id
title
game_system
created_at
updated_at
```

### documents

```text
id
campaign_id
filename
page_count
content_hash
created_at
```

### pages

```text
id
document_id
page_number
text
extraction_method
has_text
text_coverage_ratio
width
height
```

### page_blocks

```text
id
document_id
page_id
page_number
block_index
text
bbox_json
metadata_json
```

### sections

```text
id
campaign_id
document_id
parent_section_id
title
level
page_start
page_end
```

### chunks

```text
id
campaign_id
document_id
section_id
page_start
page_end
text
chunk_type
token_count
embedding
source_spans_json
metadata_json
```

### entities

```text
id
campaign_id
type
name
aliases_json
summary
player_safe_json
gm_only_json
metadata_json
confidence
embedding
created_at
updated_at
```

### entity_source_refs

```text
id
entity_id
document_id
chunk_id
page_number
evidence_excerpt
page_block_ids_json
bbox_json
```

### entity_relations

```text
id
campaign_id
from_entity_id
relation_type
to_entity_id
source_refs_json
confidence
metadata_json
```

### extraction_reviews

```text
id
campaign_id
ingestion_run_id
target_type
target_id
reviewer_model
review_prompt_version
verdict
issues_json
missing_information_json
confidence_adjustment
source_refs_json
created_at
```

### correction_attempts

```text
id
campaign_id
ingestion_run_id
target_type
target_id
review_id
original_payload_json
corrected_payload_json
correction_model
correction_prompt_version
status
created_at
```

### secrets

Secrets may be stored as typed entities, but a dedicated table can be useful.

```text
id
campaign_id
title
truth
safe_teaser
reveal_conditions_json
source_refs_json
confidence
```

### campaign_state

Runtime state for a specific table, solo run, or party.

```text
id
campaign_id
party_id
revealed_entities_json
revealed_secrets_json
visited_locations_json
met_npcs_json
active_threads_json
updated_at
```

## Retrieval Strategy

The GM Agent should not query the whole database directly. It should use a campaign retrieval service.

Useful retrieval functions:

```text
search_campaign(query, filters)
get_entity(entity_id)
get_location(location_id)
get_npc(npc_id)
get_scene_packet(scene_id, campaign_state_id)
find_relevant_secrets(context, campaign_state_id)
get_source_excerpt(chunk_id)
get_source_location(source_ref_id)
get_player_known_summary(campaign_state_id)
```

These can later be exposed as MCP tools, but MCP should not be treated as the data layer. It is an interface on top of the campaign retrieval service.

## Source PDF Display

Source display should be treated as a first-class feature.

Every extracted fact should be traceable back to:

- Original document.
- Page number.
- Chunk.
- Evidence excerpt.
- Page block IDs when available.
- Bounding box when available.

The minimum useful version is page-level linking:

```text
Open document doc_anathazerin at page 73
```

The stronger version is region-level highlighting:

```text
Open document doc_anathazerin at page 73 and highlight bbox x0/y0/x1/y1
```

A web implementation can use PDF.js to render the user's original PDF, then overlay transparent highlight rectangles based on stored PDF coordinates converted to viewport coordinates.

For MVP, page-level source references are enough. Region highlighting should be designed into the ingestion data model from the start so it can be added without re-ingesting everything.

## Scene Packets

Scene packets are runtime-ready context bundles for the GM Agent.

A scene packet should include only the information needed for the current moment of play.

Example:

```json
{
  "scene_id": "scene_arrival_at_village",
  "title": "Arrival at the Village",
  "player_visible": {
    "description": "A rain-soaked village lies under a low gray sky.",
    "available_exits": ["inn", "market", "temple"],
    "present_npcs": ["npc_mira", "npc_captain_orlan"]
  },
  "gm_only": {
    "true_situation": "The villagers are hiding evidence of cult activity.",
    "hidden_clues": ["clue_bloody_symbol"],
    "npc_agendas": [
      {
        "npc_id": "npc_mira",
        "agenda": "Protect her brother from suspicion."
      }
    ],
    "danger_triggers": [
      "If the player searches the abandoned cellar, reveal signs of recent ritual use."
    ]
  },
  "continuity": {
    "already_revealed": [],
    "must_not_reveal_yet": ["secret_cult_under_temple"]
  },
  "source_refs": [
    {
      "page": 80,
      "chunk_id": "chunk_080_001"
    }
  ]
}
```

The GM Agent receives scene packets, not the whole campaign.

## Model Usage Strategy

For OpenAI models, use cheaper models for high-volume extraction and stronger models for ambiguous reasoning.

Suggested split:

```text
Small/cheap model:
- chunk classification
- simple extraction
- tagging
- short summaries

Mid model:
- complex entity extraction
- player-safe vs GM-only split
- relation extraction
- reveal conditions
- scene packet generation
- adversarial evidence review for important entities and relations

Strong model:
- contradiction review
- difficult entity resolution
- quality audits
- benchmark generation
- sampled adversarial review of completed ingestion runs
```

The exact model names should remain configurable.

Suggested development setup:

```text
cheap extractor: gpt-5-nano
default extractor: gpt-5-mini
default reviewer: gpt-5-mini with a separate evidence-review prompt
strong reviewer: gpt-5.2 for sampled audits or difficult contradictions
```

The reviewer can use the same model family as the extractor. The important difference is the role, prompt, schema, and requirement to ground every objection in the source.

## Ingestion Output Requirements

Every extracted fact should be:

- Structured.
- Source-backed.
- Confidence-scored.
- Reviewable by an adversarial evidence reviewer.
- Traceable to an ingestion run.
- Validated against a schema.
- Correctable by a human.

Suggested metadata:

```json
{
  "ingestion_run_id": "run_2026_06_05_001",
  "model": "gpt-5.4-mini",
  "prompt_version": "entity-extraction-v3",
  "source_refs": [
    {
      "page": 42,
      "chunk_id": "chunk_042_003",
      "page_block_ids": ["block_042_006"],
      "bbox": {
        "x0": 58.0,
        "y0": 140.0,
        "x1": 520.0,
        "y1": 220.0
      }
    }
  ],
  "confidence": 0.84
}
```

## Main Risks

### Bad Chunking

If the document is chunked poorly, later extraction will be poor.

Mitigation:

- Preserve section structure.
- Store page references.
- Store page block references and source spans.
- Allow re-chunking.

### Unsupported Scanned PDFs

Scanned or image-only PDFs will not produce reliable text or source alignment.

Mitigation:

- Detect low text coverage during import.
- Reject unsupported PDFs with a clear user-facing error.
- Keep OCR out of scope until the text-based ingestion path is reliable.

### Spoilers

The system may reveal hidden truths too early.

Mitigation:

- Separate player-safe and GM-only fields.
- Model reveal conditions.
- Use runtime campaign state.
- Validate scene packets before sending them to the GM Agent.

### Hallucinated Facts

The LLM may infer plausible but unsupported campaign facts.

Mitigation:

- Require source references.
- Store confidence.
- Reject unsupported facts.
- Keep source excerpts for review.
- Run adversarial evidence review on extracted facts and relations.

### Overzealous Adversarial Review

The reviewer may object too often, invent weak objections, or create unnecessary correction loops.

Mitigation:

- Require objections to reference the source.
- Use structured verdicts.
- Limit automated correction to one pass.
- Send unresolved disputes to human review.
- Track reviewer false positives over time.

### Duplicate or Confused Entities

Long campaigns often use aliases, titles, and repeated location names.

Mitigation:

- Entity resolution pass.
- Alias tracking.
- Human review for low-confidence merges.

### Copyright and Content Boundaries

Extracted commercial content must be handled carefully.

Mitigation:

- Assume user-owned PDFs.
- Avoid public sharing of extracted campaigns.
- Avoid exports that replace the original book.
- Keep source references tied to the user's local/private document.

## Roadmap: Map and Handout Assets

Text-based ingestion does not capture image-only pages (maps, some handouts). On *Mondanités et Momie*, PDF pages 6 and 19 are full-page JPEGs with almost no extractable text.

Planned work (Stage 1 extension):

- Detect image-heavy pages during raw import (low text coverage + large embedded images).
- Extract images with page number and bounding box; store as document assets linked to `page_id`.
- Classify asset type (`map`, `handout`, `illustration`) — manually or via semantic layer later.
- Expose assets via the API alongside chunks and source references.

Handouts with a text layer are already covered by chunking; this item targets **graphical** assets only. Full-document OCR remains out of scope.

## Open Questions

- How much manual review is acceptable after ingestion?
- Should the first app be local-first to reduce copyright and privacy concerns?
- How much rules-system awareness should ingestion include?
- Should scene packets be generated ahead of time or dynamically at runtime?
- Is relationship graph exploration important for the MVP, or only for later?
- Should campaign state be per party, per solo run, or both?
- Should source highlighting be page-level in MVP or should region-level highlights ship early?
