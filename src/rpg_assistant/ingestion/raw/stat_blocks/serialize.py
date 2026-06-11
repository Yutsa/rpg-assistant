from __future__ import annotations

from typing import Any

from rpg_assistant.models.raw import ChunkRecord

_DETAIL_FIELDS = ("name", "subtitle", "nc", "attributes", "abilities", "game_system")


def stat_block_ambiguity_candidates(chunks: list[ChunkRecord]) -> list[dict[str, Any]]:
    return [
        {
            "name": (chunk.metadata.get("stat_block") or {}).get("name", ""),
            "nc": (chunk.metadata.get("stat_block") or {}).get("nc"),
            "chunk_id": chunk.id,
            "pages": {"start": chunk.page_start, "end": chunk.page_end},
        }
        for chunk in chunks
    ]


def chunk_to_list_item(chunk: ChunkRecord, *, preview_len: int = 200) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "section_id": chunk.section_id,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "chunk_type": chunk.chunk_type,
        "chunk_type_hint": chunk.chunk_type_hint,
        "token_count": chunk.token_count,
        "needs_rechunk": chunk.needs_rechunk,
        "text_preview": chunk.text[:preview_len],
    }


def chunk_to_stat_block_detail(chunk: ChunkRecord) -> dict[str, Any]:
    stat_block = chunk.metadata.get("stat_block") or {}
    detail: dict[str, Any] = {
        field: stat_block[field]
        for field in _DETAIL_FIELDS
        if field in stat_block
    }
    if "game_system" not in detail:
        game_system = chunk.metadata.get("game_system")
        if game_system:
            detail["game_system"] = game_system
    detail["chunk_id"] = chunk.id
    detail["pages"] = {"start": chunk.page_start, "end": chunk.page_end}
    detail["source_refs"] = [
        {
            "document_id": chunk.document_id,
            "page": span.page,
            "chunk_id": chunk.id,
            "page_block_ids": span.page_block_ids,
            "bbox": span.bbox.model_dump() if span.bbox else None,
        }
        for span in chunk.source_spans
    ]
    return detail
