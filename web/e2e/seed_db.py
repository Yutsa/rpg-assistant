#!/usr/bin/env python3
"""Seed a dedicated SQLite database for Playwright acceptance tests."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pymupdf

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from rpg_assistant.models.raw import (  # noqa: E402
    BBox,
    ChunkRecord,
    IngestionRunRecord,
    PageBlockRecord,
    PageRecord,
    SectionRecord,
    SourceSpan,
)
from rpg_assistant.models.semantic import EntityRecord, EntitySourceRef  # noqa: E402
from rpg_assistant.storage.db import get_connection  # noqa: E402
from rpg_assistant.storage.repositories.raw import RawRepository  # noqa: E402
from rpg_assistant.storage.repositories.semantic import SemanticRepository  # noqa: E402


def create_test_pdf(pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello adventurer — RPG Assistant e2e fixture")
    page.draw_rect(pymupdf.Rect(10, 20, 100, 40), color=(1, 0, 0), width=0.5)
    doc.save(pdf_path)
    doc.close()


def run_migrations(database_url: str) -> None:
    env = {**os.environ, "DATABASE_URL": database_url}
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )


def seed_data(repo: RawRepository, semantic: SemanticRepository, pdf_path: Path) -> None:
    repo.ensure_campaign("momie", title="Momie", game_system="cof2")
    repo.ensure_campaign("vide", title="Campagne vide", game_system="")
    repo.upsert_document(
        "doc_e2e",
        campaign_id="momie",
        filename="aventure-test.pdf",
        page_count=1,
        content_hash="e2e-hash",
    )
    repo.create_ingestion_run(
        IngestionRunRecord(
            id="run_e2e",
            campaign_id="momie",
            document_id="doc_e2e",
            stage="raw",
            status="completed",
            stats={"source_pdf_path": str(pdf_path.resolve())},
        )
    )
    repo.insert_sections(
        [
            SectionRecord(
                id="sec_intro",
                campaign_id="momie",
                document_id="doc_e2e",
                parent_section_id=None,
                title="Introduction",
                level=1,
                page_start=1,
                page_end=1,
            ),
            SectionRecord(
                id="sec_scene",
                campaign_id="momie",
                document_id="doc_e2e",
                parent_section_id="sec_intro",
                title="Scène d'ouverture",
                level=2,
                page_start=1,
                page_end=1,
            ),
        ]
    )
    repo.insert_chunks(
        [
            ChunkRecord(
                id="chunk_narrative",
                campaign_id="momie",
                document_id="doc_e2e",
                section_id="sec_scene",
                page_start=1,
                page_end=1,
                text="Hello adventurer — vous entrez dans la crypte.",
                chunk_type_hint="narrative",
                chunk_type="narrative",
                token_count=8,
                source_spans=[
                    SourceSpan(
                        page=1,
                        page_block_ids=["blk_narrative"],
                        bbox=BBox(x0=10, y0=20, x1=100, y1=40),
                    )
                ],
            ),
            ChunkRecord(
                id="chunk_gobelin",
                campaign_id="momie",
                document_id="doc_e2e",
                section_id="sec_scene",
                page_start=1,
                page_end=1,
                text="Gobelin NC 1",
                chunk_type_hint="stat_block",
                token_count=5,
                metadata={
                    "stat_block": {
                        "name": "Gobelin",
                        "nc": 1,
                        "attributes": {"FOR": "10", "AGI": "14"},
                        "abilities": [{"title": "Coup sournois", "text": "Attaque furtive."}],
                    }
                },
                source_spans=[
                    SourceSpan(page=1, page_block_ids=["blk_gobelin"], bbox=BBox(x0=50, y0=60, x1=200, y1=120))
                ],
            ),
            ChunkRecord(
                id="chunk_gobelin_dup",
                campaign_id="momie",
                document_id="doc_e2e",
                section_id="sec_scene",
                page_start=1,
                page_end=1,
                text="Gobelin NC 2 (variante)",
                chunk_type_hint="stat_block",
                token_count=6,
                metadata={
                    "stat_block": {
                        "name": "Gobelin",
                        "subtitle": "Chef de meute",
                        "nc": 2,
                        "attributes": {"FOR": "12"},
                        "abilities": [],
                    }
                },
                source_spans=[SourceSpan(page=1, page_block_ids=["blk_gobelin2"])],
            ),
            ChunkRecord(
                id="chunk_orc",
                campaign_id="momie",
                document_id="doc_e2e",
                section_id="sec_intro",
                page_start=1,
                page_end=1,
                text="Orc NC 3",
                chunk_type_hint="stat_block",
                token_count=4,
                metadata={
                    "stat_block": {
                        "name": "Orc",
                        "nc": 3,
                        "attributes": {"FOR": "16"},
                        "abilities": [{"title": "Furie", "text": "Bonus en mêlée."}],
                    }
                },
                source_spans=[SourceSpan(page=1, page_block_ids=["blk_orc"])],
            ),
        ]
    )
    repo.insert_pages(
        [
            PageRecord(
                id="page_1",
                document_id="doc_e2e",
                page_number=1,
                text="Hello adventurer",
                text_coverage_ratio=1.0,
                width=595.0,
                height=842.0,
            )
        ]
    )
    repo.insert_page_blocks(
        [
            PageBlockRecord(
                id="blk_narrative",
                document_id="doc_e2e",
                page_id="page_1",
                page_number=1,
                block_index=0,
                text="Hello adventurer",
                bbox=BBox(x0=10, y0=20, x1=100, y1=40),
            ),
            PageBlockRecord(
                id="blk_gobelin",
                document_id="doc_e2e",
                page_id="page_1",
                page_number=1,
                block_index=1,
                text="Gobelin",
                bbox=BBox(x0=50, y0=60, x1=200, y1=120),
            ),
            PageBlockRecord(
                id="blk_gobelin2",
                document_id="doc_e2e",
                page_id="page_1",
                page_number=1,
                block_index=2,
                text="Gobelin chef",
                bbox=BBox(x0=50, y0=130, x1=200, y1=180),
            ),
            PageBlockRecord(
                id="blk_orc",
                document_id="doc_e2e",
                page_id="page_1",
                page_number=1,
                block_index=3,
                text="Orc",
                bbox=BBox(x0=220, y0=60, x1=350, y1=120),
            ),
        ]
    )
    semantic.submit_entities(
        ingestion_run_id="run_sem_e2e",
        campaign_id="momie",
        submitted_by="e2e",
        entities=[
            EntityRecord(
                entity_id="ent_crypte",
                type="location",
                name="Crypte",
                summary="Lieu d'ouverture de l'aventure.",
                source_refs=[
                    EntitySourceRef(
                        document_id="doc_e2e",
                        chunk_id="chunk_narrative",
                        page=1,
                    )
                ],
                confidence=0.9,
            )
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=f"sqlite:///{REPO_ROOT / 'data' / 'e2e_test.db'}",
        help="SQLite URL for the e2e database",
    )
    parser.add_argument(
        "--pdf-path",
        type=Path,
        default=Path(__file__).parent / "fixtures" / "test.pdf",
        help="Path to the test PDF fixture",
    )
    args = parser.parse_args()

    db_path = args.database_url.replace("sqlite:///", "")
    if db_path and db_path != ":memory:":
        path = Path(db_path)
        if path.exists():
            path.unlink()

    create_test_pdf(args.pdf_path)
    run_migrations(args.database_url)

    os.environ["DATABASE_URL"] = args.database_url
    with get_connection() as conn:
        repo = RawRepository(conn)
        semantic = SemanticRepository(conn)
        seed_data(repo, semantic, args.pdf_path)

    print(f"Seeded e2e database at {args.database_url}")
    print(f"Test PDF at {args.pdf_path.resolve()}")


if __name__ == "__main__":
    main()
