from __future__ import annotations

import json

from rpg_core.stat_blocks.matching import (
    enrich_chunk_metadata,
    matches_stat_block_name,
    normalize_stat_block_key,
)
from rpg_core.stat_blocks.serialize import chunk_to_stat_block_detail
from rpg_core.models.raw import ChunkRecord, SourceSpan
from tests.fixtures.db import memory_repo as _memory_repo


def _azulria_metadata() -> dict:
    return {
        "stat_block": {
            "name": "AZULRIA",
            "subtitle": "PRÊTRESSE 7",
            "nc": 4,
            "attributes": {"AGI": 1, "FOR": 3},
            "abilities": [{"title": "PASSAGE DANS LA PIERRE", "text": "Deux fois par jour."}],
            "raw_text": "AZULRIA | NC 4",
            "block_refs": [],
            "game_system": "cof2",
        },
        "game_system": "cof2",
    }


def _seed_document(repo: RawRepository) -> None:
    with repo.conn.cursor() as cur:
        cur.execute(
            "INSERT INTO campaigns (id, title, game_system) VALUES (%s, %s, %s)",
            ("momie", "Test", "cof2"),
        )
        cur.execute(
            """
            INSERT INTO documents (id, campaign_id, filename, page_count, content_hash)
            VALUES (%s, %s, %s, %s, %s)
            """,
            ("doc_test", "momie", "test.pdf", 20, "hash"),
        )
    repo.conn.commit()


def _insert_stat_chunk(
    repo: RawRepository,
    chunk_id: str,
    metadata: dict,
    *,
    page_start: int = 15,
    page_end: int = 15,
) -> None:
    with repo.conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chunks (
                id, campaign_id, document_id, page_start, page_end,
                text, chunk_type_hint, token_count, source_spans_json, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                chunk_id,
                "momie",
                "doc_test",
                page_start,
                page_end,
                "stat text",
                "stat_block",
                10,
                json.dumps([{"page": page_start, "page_block_ids": ["pb_1"]}]),
                json.dumps(metadata),
            ),
        )
    repo.conn.commit()


def test_normalize_stat_block_key():
    assert normalize_stat_block_key("  AZULRIA  ") == "azulria"
    assert normalize_stat_block_key("PRÊTRESSE 7") == "pretresse 7"
    assert normalize_stat_block_key("ÉèÀ") == "eea"


def test_matches_stat_block_name():
    stat_block = _azulria_metadata()["stat_block"]
    assert matches_stat_block_name("AZULRIA", stat_block)
    assert matches_stat_block_name("azulria", stat_block)
    assert matches_stat_block_name("pretresse 7", stat_block)
    assert not matches_stat_block_name("UNKNOWN", stat_block)


def test_list_stat_blocks():
    repo = _memory_repo()
    _seed_document(repo)
    _insert_stat_chunk(repo, "chk_azulria", _azulria_metadata())
    _insert_stat_chunk(
        repo,
        "chk_generic",
        {"stat_block": {"name": "", "nc": None, "raw_text": "generic"}, "game_system": "generic"},
        page_start=10,
    )
    _insert_stat_chunk(
        repo,
        "chk_other",
        {
            "stat_block": {
                "name": "GOLEM",
                "nc": 6,
                "attributes": {},
                "abilities": [],
                "raw_text": "",
                "block_refs": [],
                "game_system": "cof2",
            },
            "game_system": "cof2",
        },
        page_start=18,
        page_end=19,
    )

    entries = repo.list_stat_blocks("doc_test")
    assert len(entries) == 2
    assert entries[0].name == "AZULRIA"
    assert entries[0].nc == 4
    assert entries[0].chunk_id == "chk_azulria"
    assert entries[0].pages == {"start": 15, "end": 15}
    assert entries[1].name == "GOLEM"
    assert entries[1].pages == {"start": 18, "end": 19}


def test_get_stat_block_by_name():
    repo = _memory_repo()
    _seed_document(repo)
    _insert_stat_chunk(repo, "chk_azulria", _azulria_metadata())

    result = repo.get_stat_block("doc_test", "AZULRIA")
    assert isinstance(result, ChunkRecord)
    assert result.id == "chk_azulria"

    result_ci = repo.get_stat_block("doc_test", "azulria")
    assert isinstance(result_ci, ChunkRecord)

    result_sub = repo.get_stat_block("doc_test", "pretresse 7")
    assert isinstance(result_sub, ChunkRecord)

    assert repo.get_stat_block("doc_test", "UNKNOWN") is None


def test_get_stat_block_sql_lookup_keys():
    repo = _memory_repo()
    _seed_document(repo)
    _insert_stat_chunk(repo, "chk_azulria", enrich_chunk_metadata(_azulria_metadata()))

    assert repo._stat_blocks_use_lookup_keys("doc_test") is True
    assert repo.get_stat_block("doc_test", "pretresse 7").id == "chk_azulria"
    assert repo.get_stat_block("doc_test", "UNKNOWN") is None


def test_get_stat_block_mixed_lookup_and_legacy_chunks():
    repo = _memory_repo()
    _seed_document(repo)
    _insert_stat_chunk(repo, "chk_new", enrich_chunk_metadata(_azulria_metadata()), page_start=15)
    _insert_stat_chunk(repo, "chk_legacy", _azulria_metadata(), page_start=16)

    result = repo.get_stat_block("doc_test", "azulria")
    assert isinstance(result, list)
    assert {c.id for c in result} == {"chk_new", "chk_legacy"}


def test_get_stat_block_legacy_fallback_without_lookup_keys():
    repo = _memory_repo()
    _seed_document(repo)
    _insert_stat_chunk(repo, "chk_azulria", _azulria_metadata())

    assert repo._stat_blocks_use_lookup_keys("doc_test") is False
    assert repo.get_stat_block("doc_test", "pretresse 7").id == "chk_azulria"


def test_get_stat_block_ambiguous():
    repo = _memory_repo()
    _seed_document(repo)
    _insert_stat_chunk(repo, "chk_a", _azulria_metadata(), page_start=15)
    _insert_stat_chunk(repo, "chk_b", _azulria_metadata(), page_start=16)

    result = repo.get_stat_block("doc_test", "azulria")
    assert isinstance(result, list)
    assert len(result) == 2
    assert {c.id for c in result} == {"chk_a", "chk_b"}


def test_chunk_to_stat_block_detail():
    chunk = ChunkRecord(
        id="chk_azulria",
        campaign_id="momie",
        document_id="doc_test",
        page_start=15,
        page_end=15,
        text="stat text",
        chunk_type_hint="stat_block",
        token_count=10,
        source_spans=[SourceSpan(page=15, page_block_ids=["pb_1"])],
        metadata=_azulria_metadata(),
    )
    detail = chunk_to_stat_block_detail(chunk)
    assert detail["name"] == "AZULRIA"
    assert detail["nc"] == 4
    assert detail["chunk_id"] == "chk_azulria"
    assert detail["pages"] == {"start": 15, "end": 15}
    assert detail["game_system"] == "cof2"
    assert "raw_text" not in detail
    assert "block_refs" not in detail
    assert len(detail["source_refs"]) == 1
    assert detail["source_refs"][0]["chunk_id"] == "chk_azulria"
    assert detail["source_refs"][0]["page_block_ids"] == ["pb_1"]
