"""Serveur e2e : API sous /api + SPA statique."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from rpg_assistant.api.deps import get_raw_repo, get_semantic_repo  # noqa: E402
from rpg_assistant.api.main import create_app  # noqa: E402
import rpg_assistant.api.main as api_main  # noqa: E402
from rpg_assistant.models.raw import (  # noqa: E402
    BBox,
    ChunkRecord,
    PageBlockRecord,
    PageRecord,
    SectionRecord,
    SourceSpan,
)
from rpg_assistant.storage.repositories.semantic import SemanticRepository  # noqa: E402
from tests.fixtures.db import memory_repo as _memory_repo_factory  # noqa: E402

WEB_DIST = ROOT / "web" / "dist"


def _seed_repo():
    repo = _memory_repo_factory(with_pages=True, with_semantic=True, check_same_thread=False)
    repo.ensure_campaign("momie", title="Momie", game_system="cof2")
    repo.upsert_document(
        "doc_test",
        campaign_id="momie",
        filename="test.pdf",
        page_count=1,
        content_hash="abc",
    )
    repo.insert_sections(
        [
            SectionRecord(
                id="sec_1",
                campaign_id="momie",
                document_id="doc_test",
                parent_section_id=None,
                title="Intro",
                level=1,
                page_start=1,
                page_end=1,
            )
        ]
    )
    repo.insert_chunks(
        [
            ChunkRecord(
                id="chunk_1",
                campaign_id="momie",
                document_id="doc_test",
                section_id="sec_1",
                page_start=1,
                page_end=1,
                text="Hello adventurer",
                chunk_type_hint="narrative",
                token_count=3,
                source_spans=[
                    SourceSpan(page=1, page_block_ids=["blk_1"], bbox=BBox(x0=10, y0=20, x1=100, y1=40))
                ],
            ),
            ChunkRecord(
                id="chunk_stat",
                campaign_id="momie",
                document_id="doc_test",
                section_id="sec_1",
                page_start=1,
                page_end=1,
                text="Gobelin NC 1",
                chunk_type_hint="stat_block",
                token_count=5,
                source_spans=[
                    SourceSpan(page=1, page_block_ids=["blk_1"], bbox=BBox(x0=10, y0=20, x1=100, y1=40))
                ],
                metadata={
                    "stat_block": {
                        "name": "Gobelin",
                        "nc": 1,
                        "attributes": {"FOR": "10"},
                        "abilities": [{"title": "Coup sournois", "text": "Attaque surprise."}],
                    }
                },
            ),
        ]
    )
    repo.insert_pages(
        [
            PageRecord(
                id="page_1",
                document_id="doc_test",
                page_number=1,
                text="Hello",
                text_coverage_ratio=1.0,
                width=595.0,
                height=842.0,
            )
        ]
    )
    repo.insert_page_blocks(
        [
            PageBlockRecord(
                id="blk_1",
                document_id="doc_test",
                page_id="page_1",
                page_number=1,
                block_index=0,
                text="Hello",
                bbox=BBox(x0=10, y0=20, x1=100, y1=40),
            )
        ]
    )
    return repo


def create_e2e_app() -> FastAPI:
    if not WEB_DIST.is_dir():
        msg = f"Frontend build missing: {WEB_DIST}. Run `cd web && npm run build`."
        raise FileNotFoundError(msg)

    repo = _seed_repo()
    original_dist = api_main.WEB_DIST
    api_main.WEB_DIST = Path("/tmp/rpg-assistant-no-web-dist")
    api = create_app()
    api_main.WEB_DIST = original_dist
    api.dependency_overrides[get_raw_repo] = lambda: repo
    api.dependency_overrides[get_semantic_repo] = lambda: SemanticRepository(repo.conn)

    app = FastAPI()
    app.mount("/api", api)

    assets_dir = WEB_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        candidate = WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run(create_e2e_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
