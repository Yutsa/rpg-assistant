from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from rpg_api.deps import get_raw_repo
from rpg_api.main import create_app
from rpg_api.routers import imports as imports_router
from rpg_core.models.raw import IngestionRunRecord
from rpg_ingest.raw.clojure_import import ClojureImportError, ClojureImportResult
from tests.fixtures.db import memory_repo as _memory_repo_factory


@pytest.fixture()
def api_client(tmp_path: Path) -> TestClient:
    repo = _memory_repo_factory(check_same_thread=False)
    app = create_app()
    app.dependency_overrides[get_raw_repo] = lambda: repo

    def _immediate_task(_self, func, *args, **kwargs):
        func(*args, **kwargs)

    with patch.object(imports_router, "_upload_dir", return_value=tmp_path):
        with patch("fastapi.BackgroundTasks.add_task", _immediate_task):
            with TestClient(app) as client:
                yield client

    app.dependency_overrides.clear()
    with imports_router._pending_lock:
        imports_router._pending_imports.clear()
        imports_router._run_aliases.clear()


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4 minimal\n"


def test_list_game_systems(api_client: TestClient) -> None:
    response = api_client.get("/ingestion/game-systems")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == "cof2"
    assert payload[0]["default"] is True
    assert payload[0]["supports_stat_blocks"] is True


def test_create_import_returns_202_and_polls_status(api_client: TestClient) -> None:
    mock_result = ClojureImportResult(
        ingestion_run_id="run_test_1",
        campaign_id="ma-campagne",
        document_id="doc_test_1",
        status="completed",
        stats={
            "extraction_method": "pdfbox",
            "stat_block_profile": "cof2",
            "stat_block_count": 3,
        },
    )

    repo = api_client.app.dependency_overrides[get_raw_repo]()
    repo.ensure_campaign("ma-campagne", title="Ma Campagne", game_system="cof2")
    repo.upsert_document(
        "doc_test_1",
        campaign_id="ma-campagne",
        filename="test.pdf",
        page_count=1,
        content_hash="abc",
    )
    repo.create_ingestion_run(
        IngestionRunRecord(
            id="run_test_1",
            campaign_id="ma-campagne",
            document_id="doc_test_1",
            status="completed",
            stats=mock_result.stats,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
    )

    with patch(
        "rpg_api.routers.imports.run_clojure_import",
        return_value=mock_result,
    ):
        response = api_client.post(
            "/imports",
            data={
                "campaign_id": "ma-campagne",
                "campaign_title": "Ma Campagne",
                "game_system": "cof2",
                "reimport": "true",
            },
            files={"file": ("test.pdf", BytesIO(_pdf_bytes()), "application/pdf")},
        )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "running"
    assert body["campaign_id"] == "ma-campagne"
    tracking_id = body["ingestion_run_id"]

    poll = api_client.get(f"/ingestion-runs/{tracking_id}")
    assert poll.status_code == 200
    run = poll.json()
    assert run["status"] == "completed"
    assert run["document_id"] == "doc_test_1"
    assert run["stats"]["extraction_method"] == "pdfbox"
    assert run["stats"]["stat_block_profile"] == "cof2"


def test_create_import_rejects_unknown_game_system(api_client: TestClient) -> None:
    response = api_client.post(
        "/imports",
        data={"campaign_id": "test", "game_system": "dnd5"},
        files={"file": ("test.pdf", BytesIO(_pdf_bytes()), "application/pdf")},
    )
    assert response.status_code == 422
    assert "Unknown game_system" in response.json()["error"]


def test_create_import_validates_campaign_id(api_client: TestClient) -> None:
    response = api_client.post(
        "/imports",
        data={"campaign_id": "INVALID", "game_system": "cof2"},
        files={"file": ("test.pdf", BytesIO(_pdf_bytes()), "application/pdf")},
    )
    assert response.status_code == 400


def test_create_import_validates_pdf_file(api_client: TestClient) -> None:
    response = api_client.post(
        "/imports",
        data={"campaign_id": "test", "game_system": "cof2"},
        files={"file": ("notes.txt", BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


def test_get_ingestion_run_unknown(api_client: TestClient) -> None:
    response = api_client.get("/ingestion-runs/run_missing")
    assert response.status_code == 404


def test_create_import_surfaces_rejected_run(api_client: TestClient) -> None:
    rejected = ClojureImportResult(
        ingestion_run_id="run_rejected",
        campaign_id="reject-camp",
        document_id="doc_rejected",
        status="rejected",
        error_message="PDF rejected: insufficient text coverage",
        stats={"text_coverage_ratio": 0.05, "page_count": 1},
    )

    repo = api_client.app.dependency_overrides[get_raw_repo]()
    repo.ensure_campaign("reject-camp", title="Reject Camp", game_system="cof2")
    repo.upsert_document(
        "doc_rejected",
        campaign_id="reject-camp",
        filename="tiny.pdf",
        page_count=1,
        content_hash="def",
    )
    repo.create_ingestion_run(
        IngestionRunRecord(
            id="run_rejected",
            campaign_id="reject-camp",
            document_id="doc_rejected",
            status="rejected",
            error_message=rejected.error_message,
            stats=rejected.stats,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
    )

    with patch(
        "rpg_api.routers.imports.run_clojure_import",
        side_effect=ClojureImportError("PDF rejected", result=rejected),
    ):
        response = api_client.post(
            "/imports",
            data={"campaign_id": "reject-camp", "game_system": "cof2"},
            files={"file": ("tiny.pdf", BytesIO(_pdf_bytes()), "application/pdf")},
        )

    tracking_id = response.json()["ingestion_run_id"]
    poll = api_client.get(f"/ingestion-runs/{tracking_id}")
    assert poll.status_code == 200
    run = poll.json()
    assert run["status"] == "rejected"
    assert "insufficient text coverage" in (run["error_message"] or "")
