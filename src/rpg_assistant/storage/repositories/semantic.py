from __future__ import annotations

import json
from typing import Any

from rpg_assistant.models.semantic import (
    ChunkClassification,
    EntityRecord,
    EntityRelationRecord,
)
from rpg_assistant.storage.db import DatabaseConnection
from rpg_assistant.storage.dialect import parse_json
from rpg_assistant.storage.ids import new_id


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=str)


class SemanticRepository:
    def __init__(self, conn: DatabaseConnection) -> None:
        self.conn = conn
        self.dialect = conn.dialect

    def submit_chunk_classifications(
        self,
        *,
        ingestion_run_id: str,
        campaign_id: str,
        submitted_by: str,
        classifications: list[ChunkClassification],
    ) -> int:
        count = 0
        with self.conn.cursor() as cur:
            for item in classifications:
                cur.execute(
                    f"""
                    UPDATE chunks SET
                        chunk_type = %s,
                        {self.dialect.merge_chunk_metadata_sql()}
                    WHERE id = %s AND campaign_id = %s
                    """,
                    (
                        item.chunk_type,
                        item.confidence,
                        ingestion_run_id,
                        submitted_by,
                        item.chunk_id,
                        campaign_id,
                    ),
                )
                count += cur.rowcount
        return count

    def submit_entities(
        self,
        *,
        ingestion_run_id: str,
        campaign_id: str,
        submitted_by: str,
        entities: list[EntityRecord],
    ) -> list[str]:
        inserted: list[str] = []
        with self.conn.cursor() as cur:
            for entity in entities:
                cur.execute(
                    f"""
                    INSERT INTO entities
                        (id, campaign_id, type, name, aliases_json, summary,
                         player_safe_json, gm_only_json, metadata_json, confidence,
                         ingestion_run_id, submitted_by)
                    VALUES (%s, %s, %s, %s, {self.dialect.json_param()}, %s, {self.dialect.json_param()}, {self.dialect.json_param()},
                            {self.dialect.json_param()}, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        type = EXCLUDED.type,
                        name = EXCLUDED.name,
                        aliases_json = EXCLUDED.aliases_json,
                        summary = EXCLUDED.summary,
                        player_safe_json = EXCLUDED.player_safe_json,
                        gm_only_json = EXCLUDED.gm_only_json,
                        metadata_json = EXCLUDED.metadata_json,
                        confidence = EXCLUDED.confidence,
                        ingestion_run_id = EXCLUDED.ingestion_run_id,
                        submitted_by = EXCLUDED.submitted_by,
                        updated_at = {self.dialect.now_expr()}
                    """,
                    (
                        entity.entity_id,
                        campaign_id,
                        entity.type,
                        entity.name,
                        _json_dumps(entity.aliases),
                        entity.summary,
                        _json_dumps(entity.player_safe),
                        _json_dumps(entity.gm_only),
                        _json_dumps(
                            {
                                **entity.metadata,
                                "ingestion_run_id": ingestion_run_id,
                                "submitted_by": submitted_by,
                            }
                        ),
                        entity.confidence,
                        ingestion_run_id,
                        submitted_by,
                    ),
                )
                cur.execute(
                    "DELETE FROM entity_source_refs WHERE entity_id = %s",
                    (entity.entity_id,),
                )
                for ref in entity.source_refs:
                    cur.execute(
                        f"""
                        INSERT INTO entity_source_refs
                            (id, entity_id, document_id, chunk_id, page_number,
                             evidence_excerpt, page_block_ids_json, bbox_json)
                        VALUES (%s, %s, %s, %s, %s, %s,
                                {self.dialect.json_param()}, {self.dialect.json_param()})
                        """,
                        (
                            new_id("ref"),
                            entity.entity_id,
                            ref.document_id,
                            ref.chunk_id,
                            ref.page,
                            ref.evidence_excerpt,
                            _json_dumps(ref.page_block_ids),
                            _json_dumps(ref.bbox.model_dump() if ref.bbox else None),
                        ),
                    )
                inserted.append(entity.entity_id)
        return inserted

    def submit_relations(
        self,
        *,
        ingestion_run_id: str,
        campaign_id: str,
        submitted_by: str,
        relations: list[EntityRelationRecord],
    ) -> int:
        count = 0
        with self.conn.cursor() as cur:
            for rel in relations:
                cur.execute(
                    f"""
                    INSERT INTO entity_relations
                        (id, campaign_id, from_entity_id, relation_type, to_entity_id,
                         source_refs_json, confidence, metadata_json,
                         ingestion_run_id, submitted_by)
                    VALUES (%s, %s, %s, %s, %s, {self.dialect.json_param()}, %s,
                            {self.dialect.json_param()}, %s, %s)
                    """,
                    (
                        new_id("rel"),
                        campaign_id,
                        rel.from_entity_id,
                        rel.relation_type,
                        rel.to_entity_id,
                        _json_dumps([r.model_dump() for r in rel.source_refs]),
                        rel.confidence,
                        _json_dumps(
                            {
                                **rel.metadata,
                                "ingestion_run_id": ingestion_run_id,
                                "submitted_by": submitted_by,
                            }
                        ),
                        ingestion_run_id,
                        submitted_by,
                    ),
                )
                count += 1
        return count

    def list_entity_ids(self, campaign_id: str) -> set[str]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM entities WHERE campaign_id = %s", (campaign_id,))
            return {r[0] for r in cur.fetchall()}

    def get_entities_without_source_refs(self, campaign_id: str) -> list[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.id FROM entities e
                LEFT JOIN entity_source_refs r ON r.entity_id = e.id
                WHERE e.campaign_id = %s
                GROUP BY e.id
                HAVING COUNT(r.id) = 0
                """,
                (campaign_id,),
            )
            return [r[0] for r in cur.fetchall()]

    def get_relations_with_unknown_entities(self, campaign_id: str) -> list[dict[str, str]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.id, r.from_entity_id, r.to_entity_id
                FROM entity_relations r
                WHERE r.campaign_id = %s
                  AND (
                    NOT EXISTS (SELECT 1 FROM entities e WHERE e.id = r.from_entity_id)
                    OR NOT EXISTS (SELECT 1 FROM entities e WHERE e.id = r.to_entity_id)
                  )
                """,
                (campaign_id,),
            )
            return [
                {"relation_id": r[0], "from_entity_id": r[1], "to_entity_id": r[2]}
                for r in cur.fetchall()
            ]

    def get_player_safe_entities(self, campaign_id: str) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, player_safe_json, gm_only_json
                FROM entities WHERE campaign_id = %s
                """,
                (campaign_id,),
            )
            return [
                {
                    "entity_id": r[0],
                    "player_safe": parse_json(r[1]) or {},
                    "gm_only": parse_json(r[2]) or {},
                }
                for r in cur.fetchall()
            ]

    def get_semantic_summary(self, campaign_id: str) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total,
                    {self.dialect.classified_chunks_expr()} AS classified
                FROM chunks WHERE campaign_id = %s
                """,
                (campaign_id,),
            )
            chunk_row = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) FROM entities WHERE campaign_id = %s",
                (campaign_id,),
            )
            entity_count = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM entity_relations WHERE campaign_id = %s",
                (campaign_id,),
            )
            relation_count = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*) FROM entities
                WHERE campaign_id = %s AND confidence < 0.5
                """,
                (campaign_id,),
            )
            low_confidence = cur.fetchone()[0]
        total, classified = chunk_row or (0, 0)
        return {
            "campaign_id": campaign_id,
            "chunks_total": total,
            "chunks_classified": classified,
            "entities": entity_count,
            "relations": relation_count,
            "low_confidence_entities": low_confidence,
            "needs_review": low_confidence,
        }
