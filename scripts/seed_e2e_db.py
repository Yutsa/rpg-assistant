#!/usr/bin/env python3
"""Seed a deterministic SQLite database for Playwright e2e tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "e2e_rpg_assistant.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"


def main() -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    env = os.environ.copy()
    env["DATABASE_URL"] = DATABASE_URL
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )

    from rpg_core.models.raw import ChunkRecord, SectionRecord
    from rpg_core.storage.db import _open_connection
    from rpg_core.storage.repositories.raw import RawRepository

    repo = RawRepository(_open_connection(DATABASE_URL))
    repo.ensure_campaign("campaign_e2e", title="Campagne E2E", game_system="cof2")
    repo.upsert_document(
        "doc_e2e",
        campaign_id="campaign_e2e",
        filename="aventure-e2e.pdf",
        page_count=3,
        content_hash="e2e-hash",
    )
    repo.insert_sections(
        [
            SectionRecord(
                id="sec_intro",
                campaign_id="campaign_e2e",
                document_id="doc_e2e",
                parent_section_id=None,
                title="Introduction",
                level=1,
                page_start=1,
                page_end=1,
            ),
            SectionRecord(
                id="sec_ch1",
                campaign_id="campaign_e2e",
                document_id="doc_e2e",
                parent_section_id="sec_intro",
                title="Chapitre 1",
                level=2,
                page_start=2,
                page_end=2,
            ),
            SectionRecord(
                id="sec_annex",
                campaign_id="campaign_e2e",
                document_id="doc_e2e",
                parent_section_id=None,
                title="Annexes",
                level=1,
                page_start=3,
                page_end=3,
            ),
        ]
    )
    repo.insert_chunks(
        [
            ChunkRecord(
                id="chunk_intro",
                campaign_id="campaign_e2e",
                document_id="doc_e2e",
                section_id="sec_intro",
                page_start=1,
                page_end=1,
                text="Bienvenue dans l'aventure E2E. Les héros arrivent au village.",
                chunk_type_hint="narrative",
                token_count=12,
            ),
            ChunkRecord(
                id="chunk_ch1",
                campaign_id="campaign_e2e",
                document_id="doc_e2e",
                section_id="sec_ch1",
                page_start=2,
                page_end=2,
                text="Le chapitre 1 commence dans la taverne du village.",
                chunk_type_hint="narrative",
                token_count=10,
            ),
            ChunkRecord(
                id="chunk_ch1b",
                campaign_id="campaign_e2e",
                document_id="doc_e2e",
                section_id="sec_ch1",
                page_start=2,
                page_end=2,
                text="Un message secret est glissé sous la porte.",
                chunk_type_hint="clue",
                token_count=9,
            ),
            ChunkRecord(
                id="chunk_stat_gobelin",
                campaign_id="campaign_e2e",
                document_id="doc_e2e",
                section_id="sec_annex",
                page_start=3,
                page_end=3,
                text="Gobelin NC 1",
                chunk_type_hint="stat_block",
                token_count=4,
                metadata={
                    "stat_block": {
                        "name": "Gobelin",
                        "nc": 1,
                        "attributes": {"FOR": "10", "DEX": "14"},
                        "abilities": ["Coup sournois"],
                    }
                },
            ),
            ChunkRecord(
                id="chunk_stat_orc",
                campaign_id="campaign_e2e",
                document_id="doc_e2e",
                section_id="sec_annex",
                page_start=3,
                page_end=3,
                text="Orc NC 3",
                chunk_type_hint="stat_block",
                token_count=4,
                metadata={
                    "stat_block": {
                        "name": "Orc",
                        "nc": 3,
                        "attributes": {"FOR": "16", "DEX": "8"},
                        "abilities": ["Furie"],
                    }
                },
            ),
        ]
    )
    repo.conn.commit()
    print(f"Seeded e2e database at {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
