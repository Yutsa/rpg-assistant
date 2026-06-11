from __future__ import annotations

from typing import Any

from rpg_assistant.models.raw import ChunkRecord

_DETAIL_FIELDS = ("name", "subtitle", "nc", "attributes", "abilities", "game_system")


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
