from __future__ import annotations

from rpg_assistant.models.raw import IngestionRunRecord
from tests.fixtures.db import memory_repo as _memory_repo


def test_list_campaigns_and_documents():
    repo = _memory_repo()
    repo.ensure_campaign("momie", title="Mondanités et Momie", game_system="cof2")
    repo.upsert_document(
        "doc_1",
        campaign_id="momie",
        filename="momie.pdf",
        page_count=20,
        content_hash="abc",
    )
    repo.create_ingestion_run(
        IngestionRunRecord(
            id="run_1",
            campaign_id="momie",
            document_id="doc_1",
            stage="raw",
            status="completed",
        )
    )

    campaigns = repo.list_campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].id == "momie"
    assert campaigns[0].title == "Mondanités et Momie"
    assert campaigns[0].document_count == 1

    documents = repo.list_documents("momie")
    assert len(documents) == 1
    assert documents[0].id == "doc_1"
    assert documents[0].filename == "momie.pdf"
    assert documents[0].latest_ingestion_run_id == "run_1"
    assert documents[0].latest_ingestion_status == "completed"

    assert repo.list_documents("unknown") == []
