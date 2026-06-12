from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from rpg_assistant.ingestion.raw.stat_blocks.matching import matches_stat_block_name
from rpg_assistant.models.raw import (
    CampaignRecord,
    ChunkRecord,
    DocumentRecord,
    IngestionRunRecord,
    PageBlockRecord,
    PageRecord,
    SectionRecord,
    SourceSpan,
    StatBlockIndexEntry,
)
from rpg_assistant.models.raw import BBox
from rpg_assistant.storage.db import DatabaseConnection
from rpg_assistant.storage.dialect import dump_json, parse_json


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RawRepository:
    def __init__(self, conn: DatabaseConnection) -> None:
        self.conn = conn
        self.dialect = conn.dialect

    def ensure_campaign(self, campaign_id: str, title: str = "", game_system: str = "") -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO campaigns (id, title, game_system)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (campaign_id, title or campaign_id, game_system),
            )

    def upsert_document(
        self,
        document_id: str,
        campaign_id: str,
        filename: str,
        page_count: int,
        content_hash: str,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (id, campaign_id, filename, page_count, content_hash)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    filename = EXCLUDED.filename,
                    page_count = EXCLUDED.page_count,
                    content_hash = EXCLUDED.content_hash
                """,
                (document_id, campaign_id, filename, page_count, content_hash),
            )

    def create_ingestion_run(self, run: IngestionRunRecord) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO ingestion_runs
                    (id, campaign_id, document_id, stage, status, error_message, stats, started_at)
                VALUES (%s, %s, %s, %s, %s, %s, {self.dialect.json_param()}, %s)
                """,
                (
                    run.id,
                    run.campaign_id,
                    run.document_id,
                    run.stage,
                    run.status,
                    run.error_message,
                    dump_json(run.stats),
                    run.started_at or _utcnow(),
                ),
            )

    def update_ingestion_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        document_id: str | None = None,
        error_message: str | None = None,
        stats: dict[str, Any] | None = None,
        finished: bool = False,
    ) -> None:
        fields: list[str] = []
        values: list[Any] = []
        if status is not None:
            fields.append("status = %s")
            values.append(status)
        if document_id is not None:
            fields.append("document_id = %s")
            values.append(document_id)
        if error_message is not None:
            fields.append("error_message = %s")
            values.append(error_message)
        if stats is not None:
            fields.append(f"stats = {self.dialect.json_param()}")
            values.append(dump_json(stats))
        if finished:
            fields.append("finished_at = %s")
            values.append(_utcnow())
        if not fields:
            return
        values.append(run_id)
        with self.conn.cursor() as cur:
            cur.execute(
                f"UPDATE ingestion_runs SET {', '.join(fields)} WHERE id = %s",
                values,
            )

    def campaign_exists(self, campaign_id: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM campaigns WHERE id = %s", (campaign_id,))
            return cur.fetchone() is not None

    def list_campaigns(self) -> list[CampaignRecord]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.title, c.game_system, c.created_at, c.updated_at,
                       COUNT(d.id) AS document_count
                FROM campaigns c
                LEFT JOIN documents d ON d.campaign_id = c.id
                GROUP BY c.id, c.title, c.game_system, c.created_at, c.updated_at
                ORDER BY c.updated_at DESC, c.id
                """
            )
            rows = cur.fetchall()
        return [
            CampaignRecord(
                id=r[0],
                title=r[1],
                game_system=r[2] or "",
                created_at=r[3],
                updated_at=r[4],
                document_count=r[5] or 0,
            )
            for r in rows
        ]

    def list_documents(self, campaign_id: str) -> list[DocumentRecord]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id, d.campaign_id, d.filename, d.page_count, d.content_hash,
                       d.created_at,
                       (SELECT COUNT(*) FROM sections s WHERE s.document_id = d.id),
                       (SELECT COUNT(*) FROM chunks ch WHERE ch.document_id = d.id),
                       (
                           SELECT ir.id
                           FROM ingestion_runs ir
                           WHERE ir.document_id = d.id AND ir.stage = 'raw'
                           ORDER BY ir.started_at DESC
                           LIMIT 1
                       ),
                       (
                           SELECT ir.status
                           FROM ingestion_runs ir
                           WHERE ir.document_id = d.id AND ir.stage = 'raw'
                           ORDER BY ir.started_at DESC
                           LIMIT 1
                       )
                FROM documents d
                WHERE d.campaign_id = %s
                ORDER BY d.created_at DESC, d.filename
                """,
                (campaign_id,),
            )
            rows = cur.fetchall()
        return [
            DocumentRecord(
                id=r[0],
                campaign_id=r[1],
                filename=r[2],
                page_count=r[3] or 0,
                content_hash=r[4],
                created_at=r[5],
                section_count=r[6] or 0,
                chunk_count=r[7] or 0,
                latest_ingestion_run_id=r[8],
                latest_ingestion_status=r[9],
            )
            for r in rows
        ]

    def get_document(self, document_id: str) -> DocumentRecord | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id, d.campaign_id, d.filename, d.page_count, d.content_hash,
                       d.created_at,
                       (SELECT COUNT(*) FROM sections s WHERE s.document_id = d.id),
                       (SELECT COUNT(*) FROM chunks ch WHERE ch.document_id = d.id),
                       (
                           SELECT ir.id
                           FROM ingestion_runs ir
                           WHERE ir.document_id = d.id AND ir.stage = 'raw'
                           ORDER BY ir.started_at DESC
                           LIMIT 1
                       ),
                       (
                           SELECT ir.status
                           FROM ingestion_runs ir
                           WHERE ir.document_id = d.id AND ir.stage = 'raw'
                           ORDER BY ir.started_at DESC
                           LIMIT 1
                       )
                FROM documents d
                WHERE d.id = %s
                """,
                (document_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return DocumentRecord(
            id=row[0],
            campaign_id=row[1],
            filename=row[2],
            page_count=row[3] or 0,
            content_hash=row[4],
            created_at=row[5],
            section_count=row[6] or 0,
            chunk_count=row[7] or 0,
            latest_ingestion_run_id=row[8],
            latest_ingestion_status=row[9],
        )

    def get_page(self, document_id: str, page_number: int) -> PageRecord | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, document_id, page_number, text, extraction_method,
                       has_text, text_coverage_ratio, width, height
                FROM pages
                WHERE document_id = %s AND page_number = %s
                """,
                (document_id, page_number),
            )
            row = cur.fetchone()
        if not row:
            return None
        return PageRecord(
            id=row[0],
            document_id=row[1],
            page_number=row[2],
            text=row[3],
            extraction_method=row[4] or "pymupdf",
            has_text=bool(row[5]),
            text_coverage_ratio=row[6] or 0.0,
            width=row[7],
            height=row[8],
        )

    def list_page_blocks_for_page(
        self, document_id: str, page_number: int
    ) -> list[PageBlockRecord]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, document_id, page_id, page_number, block_index, text,
                       bbox_json, metadata_json
                FROM page_blocks
                WHERE document_id = %s AND page_number = %s
                ORDER BY block_index
                """,
                (document_id, page_number),
            )
            rows = cur.fetchall()
        return [self._row_to_page_block(r) for r in rows]

    def get_latest_raw_run(self, document_id: str) -> IngestionRunRecord | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, campaign_id, document_id, stage, status, error_message,
                       stats, started_at, finished_at
                FROM ingestion_runs
                WHERE document_id = %s AND stage = 'raw' AND status = 'completed'
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (document_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return IngestionRunRecord(
            id=row[0],
            campaign_id=row[1],
            document_id=row[2],
            stage=row[3],
            status=row[4],
            error_message=row[5],
            stats=parse_json(row[6]) or {},
            started_at=row[7],
            finished_at=row[8],
        )

    def get_ingestion_run(self, run_id: str) -> IngestionRunRecord | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, campaign_id, document_id, stage, status, error_message,
                       stats, started_at, finished_at
                FROM ingestion_runs WHERE id = %s
                """,
                (run_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return IngestionRunRecord(
            id=row[0],
            campaign_id=row[1],
            document_id=row[2],
            stage=row[3],
            status=row[4],
            error_message=row[5],
            stats=parse_json(row[6]) or {},
            started_at=row[7],
            finished_at=row[8],
        )

    def delete_document_raw_data(self, document_id: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
            cur.execute("DELETE FROM sections WHERE document_id = %s", (document_id,))
            cur.execute("DELETE FROM page_blocks WHERE document_id = %s", (document_id,))
            cur.execute("DELETE FROM pages WHERE document_id = %s", (document_id,))

    def insert_pages(self, pages: list[PageRecord]) -> None:
        if not pages:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO pages
                    (id, document_id, page_number, text, extraction_method,
                     has_text, text_coverage_ratio, width, height)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id, page_number) DO UPDATE SET
                    text = EXCLUDED.text,
                    extraction_method = EXCLUDED.extraction_method,
                    has_text = EXCLUDED.has_text,
                    text_coverage_ratio = EXCLUDED.text_coverage_ratio,
                    width = EXCLUDED.width,
                    height = EXCLUDED.height
                """,
                [
                    (
                        p.id,
                        p.document_id,
                        p.page_number,
                        p.text,
                        p.extraction_method,
                        p.has_text,
                        p.text_coverage_ratio,
                        p.width,
                        p.height,
                    )
                    for p in pages
                ],
            )

    def insert_page_blocks(self, blocks: list[PageBlockRecord]) -> None:
        if not blocks:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                f"""
                INSERT INTO page_blocks
                    (id, document_id, page_id, page_number, block_index, text,
                     bbox_json, metadata_json)
                VALUES (%s, %s, %s, %s, %s, %s, {self.dialect.json_param()}, {self.dialect.json_param()})
                ON CONFLICT (id) DO UPDATE SET
                    text = EXCLUDED.text,
                    bbox_json = EXCLUDED.bbox_json,
                    metadata_json = EXCLUDED.metadata_json
                """,
                [
                    (
                        b.id,
                        b.document_id,
                        b.page_id,
                        b.page_number,
                        b.block_index,
                        b.text,
                        dump_json(b.bbox.model_dump()),
                        dump_json(b.metadata),
                    )
                    for b in blocks
                ],
            )

    def insert_sections(self, sections: list[SectionRecord]) -> None:
        if not sections:
            return
        by_id = {section.id: section for section in sections}
        ordered: list[SectionRecord] = []
        inserted: set[str] = set()

        def append_parent_first(section: SectionRecord) -> None:
            if section.id in inserted:
                return
            parent_id = section.parent_section_id
            if parent_id and parent_id in by_id:
                append_parent_first(by_id[parent_id])
            ordered.append(section)
            inserted.add(section.id)

        for section in sections:
            append_parent_first(section)

        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO sections
                    (id, campaign_id, document_id, parent_section_id, title, level,
                     page_start, page_end)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    parent_section_id = EXCLUDED.parent_section_id,
                    title = EXCLUDED.title,
                    level = EXCLUDED.level,
                    page_start = EXCLUDED.page_start,
                    page_end = EXCLUDED.page_end
                """,
                [
                    (
                        s.id,
                        s.campaign_id,
                        s.document_id,
                        s.parent_section_id,
                        s.title,
                        s.level,
                        s.page_start,
                        s.page_end,
                    )
                    for s in ordered
                ],
            )

    def insert_chunks(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                f"""
                INSERT INTO chunks
                    (id, campaign_id, document_id, section_id, page_start, page_end,
                     text, chunk_type, chunk_type_hint, token_count, source_spans_json,
                     metadata_json, needs_rechunk)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, {self.dialect.json_param()}, {self.dialect.json_param()}, %s)
                ON CONFLICT (id) DO UPDATE SET
                    text = EXCLUDED.text,
                    chunk_type = EXCLUDED.chunk_type,
                    chunk_type_hint = EXCLUDED.chunk_type_hint,
                    token_count = EXCLUDED.token_count,
                    source_spans_json = EXCLUDED.source_spans_json,
                    metadata_json = EXCLUDED.metadata_json,
                    needs_rechunk = EXCLUDED.needs_rechunk
                """,
                [
                    (
                        c.id,
                        c.campaign_id,
                        c.document_id,
                        c.section_id,
                        c.page_start,
                        c.page_end,
                        c.text,
                        c.chunk_type,
                        c.chunk_type_hint,
                        c.token_count,
                        dump_json([s.model_dump() for s in c.source_spans]),
                        dump_json(c.metadata),
                        c.needs_rechunk,
                    )
                    for c in chunks
                ],
            )

    def list_sections(self, document_id: str) -> list[SectionRecord]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, campaign_id, document_id, parent_section_id, title,
                       level, page_start, page_end
                FROM sections
                WHERE document_id = %s
                ORDER BY page_start, level, title
                """,
                (document_id,),
            )
            rows = cur.fetchall()
        return [
            SectionRecord(
                id=r[0],
                campaign_id=r[1],
                document_id=r[2],
                parent_section_id=r[3],
                title=r[4],
                level=r[5],
                page_start=r[6],
                page_end=r[7],
            )
            for r in rows
        ]

    def list_chunks(
        self,
        document_id: str,
        *,
        section_id: str | None = None,
        page_start: int | None = None,
        page_end: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChunkRecord]:
        clauses = ["document_id = %s"]
        params: list[Any] = [document_id]
        if section_id:
            clauses.append("section_id = %s")
            params.append(section_id)
        if page_start is not None:
            clauses.append("page_end >= %s")
            params.append(page_start)
        if page_end is not None:
            clauses.append("page_start <= %s")
            params.append(page_end)
        params.extend([limit, offset])
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, campaign_id, document_id, section_id, page_start, page_end,
                       text, chunk_type, chunk_type_hint, token_count,
                       source_spans_json, metadata_json, needs_rechunk
                FROM chunks
                WHERE {' AND '.join(clauses)}
                ORDER BY page_start, id
                LIMIT %s OFFSET %s
                """,
                params,
            )
            rows = cur.fetchall()
        return [self._row_to_chunk(r) for r in rows]

    def list_chunks_for_sections(
        self,
        document_id: str,
        section_ids: list[str],
    ) -> dict[str, list[ChunkRecord]]:
        if not section_ids:
            return {}
        in_clause, in_params = self.dialect.in_list_clause("section_id", section_ids)
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, campaign_id, document_id, section_id, page_start, page_end,
                       text, chunk_type, chunk_type_hint, token_count,
                       source_spans_json, metadata_json, needs_rechunk
                FROM chunks
                WHERE document_id = %s AND {in_clause}
                ORDER BY section_id, page_start, id
                """,
                [document_id, *in_params],
            )
            rows = cur.fetchall()
        result: dict[str, list[ChunkRecord]] = {sid: [] for sid in section_ids}
        for row in rows:
            chunk = self._row_to_chunk(row)
            if chunk.section_id:
                result.setdefault(chunk.section_id, []).append(chunk)
        return result

    def list_stat_blocks(self, document_id: str) -> list[StatBlockIndexEntry]:
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, page_start, page_end,
                       {self.dialect.stat_block_name_expr()},
                       {self.dialect.stat_block_nc_expr()}
                FROM chunks
                WHERE document_id = %s AND chunk_type_hint = 'stat_block'
                ORDER BY page_start, id
                """,
                (document_id,),
            )
            rows = cur.fetchall()
        entries: list[StatBlockIndexEntry] = []
        for row in rows:
            name = row[3]
            if not name:
                continue
            nc = row[4]
            if nc is not None and not isinstance(nc, int):
                try:
                    nc = int(nc)
                except (TypeError, ValueError):
                    nc = None
            entries.append(
                StatBlockIndexEntry(
                    name=name,
                    nc=nc,
                    chunk_id=row[0],
                    pages={"start": row[1], "end": row[2]},
                )
            )
        return entries

    def get_stat_block(
        self, document_id: str, name: str
    ) -> ChunkRecord | list[ChunkRecord] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, campaign_id, document_id, section_id, page_start, page_end,
                       text, chunk_type, chunk_type_hint, token_count,
                       source_spans_json, metadata_json, needs_rechunk
                FROM chunks
                WHERE document_id = %s AND chunk_type_hint = 'stat_block'
                ORDER BY page_start, id
                """,
                (document_id,),
            )
            rows = cur.fetchall()
        matches = [
            self._row_to_chunk(row)
            for row in rows
            if matches_stat_block_name(name, parse_json(row[11]).get("stat_block") or {})
        ]
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        return matches

    def get_chunk(self, chunk_id: str) -> ChunkRecord | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, campaign_id, document_id, section_id, page_start, page_end,
                       text, chunk_type, chunk_type_hint, token_count,
                       source_spans_json, metadata_json, needs_rechunk
                FROM chunks WHERE id = %s
                """,
                (chunk_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_chunk(row)

    def chunk_exists(self, chunk_id: str) -> bool:
        return chunk_id in self.chunks_exist([chunk_id])

    def chunks_exist(self, chunk_ids: list[str]) -> set[str]:
        if not chunk_ids:
            return set()
        in_clause, in_params = self.dialect.in_list_clause("id", chunk_ids)
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT id FROM chunks WHERE {in_clause}", in_params)
            return {r[0] for r in cur.fetchall()}

    def section_ids_with_chunks(self, document_id: str) -> set[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT section_id FROM chunks
                WHERE document_id = %s AND section_id IS NOT NULL
                """,
                (document_id,),
            )
            return {r[0] for r in cur.fetchall()}

    def get_page_blocks(self, block_ids: list[str]) -> list[PageBlockRecord]:
        if not block_ids:
            return []
        in_clause, in_params = self.dialect.in_list_clause("id", block_ids)
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, document_id, page_id, page_number, block_index, text,
                       bbox_json, metadata_json
                FROM page_blocks WHERE {in_clause}
                ORDER BY page_number, block_index
                """,
                in_params,
            )
            rows = cur.fetchall()
        return [self._row_to_page_block(r) for r in rows]

    def page_block_ids_exist(self, block_ids: list[str], document_id: str) -> set[str]:
        if not block_ids:
            return set()
        in_clause, in_params = self.dialect.in_list_clause("id", block_ids)
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id FROM page_blocks
                WHERE {in_clause} AND document_id = %s
                """,
                [*in_params, document_id],
            )
            return {r[0] for r in cur.fetchall()}

    def get_document_id_for_chunk(self, chunk_id: str) -> str | None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT document_id FROM chunks WHERE id = %s", (chunk_id,))
            row = cur.fetchone()
        return row[0] if row else None

    def _row_to_page_block(self, row: tuple) -> PageBlockRecord:
        return PageBlockRecord(
            id=row[0],
            document_id=row[1],
            page_id=row[2],
            page_number=row[3],
            block_index=row[4],
            text=row[5],
            bbox=BBox(**parse_json(row[6])),
            metadata=parse_json(row[7]) or {},
        )

    def _row_to_chunk(self, row: tuple) -> ChunkRecord:
        spans_data = parse_json(row[10]) or []
        return ChunkRecord(
            id=row[0],
            campaign_id=row[1],
            document_id=row[2],
            section_id=row[3],
            page_start=row[4],
            page_end=row[5],
            text=row[6],
            chunk_type=row[7],
            chunk_type_hint=row[8],
            token_count=row[9],
            source_spans=[SourceSpan(**s) for s in spans_data],
            metadata=parse_json(row[11]) or {},
            needs_rechunk=row[12] or False,
        )
