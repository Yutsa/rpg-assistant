from __future__ import annotations

import socket
import threading
import time
from collections.abc import Generator
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import Page

from rpg_assistant.api.deps import get_raw_repo, get_semantic_repo
from rpg_assistant.api.main import create_app
from rpg_assistant.models.raw import (
    BBox,
    ChunkRecord,
    PageBlockRecord,
    PageRecord,
    SectionRecord,
    SourceSpan,
)
from rpg_assistant.storage.repositories.semantic import SemanticRepository
from tests.fixtures.db import memory_repo as _memory_repo_factory

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = REPO_ROOT / "web-cljs" / "dist"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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
                metadata={
                    "stat_block": {
                        "name": "Gobelin",
                        "nc": 1,
                        "attributes": {"FOR": "10"},
                        "abilities": ["Coup sournois"],
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


@pytest.fixture(scope="session")
def acceptance_base_url() -> Generator[str, None, None]:
    if not (WEB_DIST / "index.html").is_file():
        pytest.skip("web-cljs/dist missing — run: cd web-cljs && npm run build")

    repo = _seed_repo()
    app = create_app()

    def _override_raw_repo():
        return repo

    def _override_semantic_repo():
        return SemanticRepository(repo.conn)

    app.dependency_overrides[get_raw_repo] = _override_raw_repo
    app.dependency_overrides[get_semantic_repo] = _override_semantic_repo

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        pytest.fail("Acceptance server did not start")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture()
def page(page: Page, acceptance_base_url: str) -> Page:
    page.goto(acceptance_base_url)
    return page
