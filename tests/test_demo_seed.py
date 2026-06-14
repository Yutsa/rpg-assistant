from __future__ import annotations

from rpg_assistant.dev.demo_seed import seed_demo_data
from rpg_assistant.storage.db import get_connection
from rpg_assistant.storage.repositories.raw import RawRepository


def test_seed_demo_data_populates_campaign() -> None:
    result = seed_demo_data(reset=True)
    with get_connection() as conn:
        repo = RawRepository(conn)
        campaigns = repo.list_campaigns()
        assert any(c.id == result["campaign_id"] for c in campaigns)
        docs = repo.list_documents(result["campaign_id"])
        assert any(d.id == result["document_id"] for d in docs)
        sections = repo.list_sections(result["document_id"])
        assert len(sections) >= 3
        chunks = repo.list_chunks(result["document_id"], section_id="sec_crypte")
        assert len(chunks) >= 2
