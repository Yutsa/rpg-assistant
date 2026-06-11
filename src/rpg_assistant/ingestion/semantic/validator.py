from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from rpg_assistant.ingestion.semantic.schemas import CHUNK_TYPES, GM_ONLY_KEYWORDS
from rpg_assistant.storage.db import DatabaseConnection
from rpg_assistant.storage.dialect import parse_json
from rpg_assistant.storage.repositories.raw import RawRepository
from rpg_assistant.storage.repositories.semantic import SemanticRepository


@dataclass
class ValidationError:
    code: str
    message: str
    target_type: str | None = None
    target_id: str | None = None


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [e.__dict__ for e in self.errors],
            "warnings": [e.__dict__ for e in self.warnings],
        }


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(v) for v in value)
    return str(value)


def _contains_gm_only_leak(text: str) -> str | None:
    lowered = text.lower()
    for keyword in GM_ONLY_KEYWORDS:
        if keyword in lowered:
            return keyword
    if re.search(r"\bthe truth is\b", lowered):
        return "the truth is"
    return None


def validate_semantic_layer(conn: DatabaseConnection, campaign_id: str) -> ValidationResult:
    raw_repo = RawRepository(conn)
    semantic_repo = SemanticRepository(conn)
    result = ValidationResult(valid=True)

    entities_without_refs = semantic_repo.get_entities_without_source_refs(campaign_id)
    for entity_id in entities_without_refs:
        result.valid = False
        result.errors.append(
            ValidationError(
                code="missing_source_ref",
                message="Entity has no source references.",
                target_type="entity",
                target_id=entity_id,
            )
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.id, r.chunk_id
            FROM entities e
            JOIN entity_source_refs r ON r.entity_id = e.id
            WHERE e.campaign_id = %s
            """,
            (campaign_id,),
        )
        for entity_id, chunk_id in cur.fetchall():
            if not raw_repo.chunk_exists(chunk_id):
                result.valid = False
                result.errors.append(
                    ValidationError(
                        code="unknown_chunk_id",
                        message=f"Entity references unknown chunk_id: {chunk_id}",
                        target_type="entity",
                        target_id=entity_id,
                    )
                )

        cur.execute(
            """
            SELECT e.id, r.page_block_ids_json, r.chunk_id
            FROM entities e
            JOIN entity_source_refs r ON r.entity_id = e.id
            WHERE e.campaign_id = %s AND r.page_block_ids_json IS NOT NULL
            """,
            (campaign_id,),
        )
        for entity_id, block_ids_json, chunk_id in cur.fetchall():
            block_ids = parse_json(block_ids_json) or []
            if not block_ids:
                continue
            document_id = raw_repo.get_document_id_for_chunk(chunk_id)
            if not document_id:
                continue
            existing = raw_repo.page_block_ids_exist(block_ids, document_id)
            missing = [bid for bid in block_ids if bid not in existing]
            if missing:
                result.valid = False
                result.errors.append(
                    ValidationError(
                        code="unknown_page_block_id",
                        message=f"Entity references unknown page_block_ids: {missing}",
                        target_type="entity",
                        target_id=entity_id,
                    )
                )

        cur.execute(
            """
            SELECT id, chunk_type, metadata_json
            FROM chunks
            WHERE campaign_id = %s AND chunk_type IS NOT NULL
            """,
            (campaign_id,),
        )
        for chunk_id_val, chunk_type, metadata in cur.fetchall():
            if chunk_type not in CHUNK_TYPES:
                result.valid = False
                result.errors.append(
                    ValidationError(
                        code="invalid_chunk_type",
                        message=f"Invalid chunk_type: {chunk_type}",
                        target_type="chunk",
                        target_id=chunk_id_val,
                    )
                )
            confidence = (parse_json(metadata) or {}).get("classification_confidence")
            if confidence is not None and not (0 <= float(confidence) <= 1):
                result.valid = False
                result.errors.append(
                    ValidationError(
                        code="invalid_confidence",
                        message=f"Classification confidence out of range: {confidence}",
                        target_type="chunk",
                        target_id=chunk_id_val,
                    )
                )

    for rel in semantic_repo.get_relations_with_unknown_entities(campaign_id):
        result.valid = False
        result.errors.append(
            ValidationError(
                code="unknown_entity_in_relation",
                message=(
                    f"Relation references unknown entities: "
                    f"{rel['from_entity_id']} -> {rel['to_entity_id']}"
                ),
                target_type="relation",
                target_id=rel["relation_id"],
            )
        )

    for entity in semantic_repo.get_player_safe_entities(campaign_id):
        player_text = _flatten_text(entity["player_safe"])
        leak = _contains_gm_only_leak(player_text)
        if leak:
            result.valid = False
            result.errors.append(
                ValidationError(
                    code="player_safe_spoiler",
                    message=f"player_safe contains GM-only keyword: {leak!r}",
                    target_type="entity",
                    target_id=entity["entity_id"],
                )
            )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, confidence FROM entities
            WHERE campaign_id = %s AND (confidence < 0 OR confidence > 1)
            """,
            (campaign_id,),
        )
        for entity_id, confidence in cur.fetchall():
            result.valid = False
            result.errors.append(
                ValidationError(
                    code="invalid_confidence",
                    message=f"Entity confidence out of range: {confidence}",
                    target_type="entity",
                    target_id=entity_id,
                )
            )

        cur.execute(
            """
            SELECT id, confidence FROM entity_relations
            WHERE campaign_id = %s AND (confidence < 0 OR confidence > 1)
            """,
            (campaign_id,),
        )
        for relation_id, confidence in cur.fetchall():
            result.valid = False
            result.errors.append(
                ValidationError(
                    code="invalid_confidence",
                    message=f"Relation confidence out of range: {confidence}",
                    target_type="relation",
                    target_id=relation_id,
                )
            )

        cur.execute(
            """
            SELECT id, source_refs_json FROM entity_relations
            WHERE campaign_id = %s
            """,
            (campaign_id,),
        )
        for relation_id, source_refs in cur.fetchall():
            refs = parse_json(source_refs) or []
            if not refs:
                result.warnings.append(
                    ValidationError(
                        code="relation_missing_source_ref",
                        message="Relation has no source references.",
                        target_type="relation",
                        target_id=relation_id,
                    )
                )
                continue
            for ref in refs:
                chunk_id = ref.get("chunk_id")
                if chunk_id and not raw_repo.chunk_exists(chunk_id):
                    result.valid = False
                    result.errors.append(
                        ValidationError(
                            code="unknown_chunk_id",
                            message=f"Relation references unknown chunk_id: {chunk_id}",
                            target_type="relation",
                            target_id=relation_id,
                        )
                    )

    return result


def validation_result_json(result: ValidationResult) -> str:
    return json.dumps(result.to_dict(), indent=2)
