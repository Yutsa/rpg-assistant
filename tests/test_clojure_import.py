from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pymupdf
import pytest

from rpg_ingest.raw.clojure_import import ClojureImportError, run_clojure_import


def _clojure_available() -> bool:
    if shutil.which("clojure") is None:
        return False
    try:
        subprocess.run(["clojure", "--version"], capture_output=True, check=True, timeout=30)
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def _make_text_pdf(path: Path, lines: list[str]) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72.0
    for line in lines:
        page.insert_text((72, y), line, fontsize=12)
        y += 24
    doc.save(path)
    doc.close()


@pytest.mark.skipif(not _clojure_available(), reason="Clojure CLI not available")
def test_run_clojure_import_completes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "import.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from alembic import command
    from alembic.config import Config

    from rpg_core.storage import db as db_module

    db_module._engine = None
    cfg = Config("/workspace/alembic.ini")
    command.upgrade(cfg, "head")

    pdf_path = tmp_path / "campaign.pdf"
    filler = "Lorem ipsum dolor sit amet. " * 120
    _make_text_pdf(pdf_path, [filler, filler])

    result = run_clojure_import(
        pdf_path,
        campaign_id="ui-import-test",
        campaign_title="UI Import Test",
        game_system="cof2",
        db_path=db_path,
        coverage_threshold=0.0,
        timeout_s=600,
    )

    assert result.status == "completed"
    assert result.ingestion_run_id.startswith("run_")
    assert result.document_id is not None
    assert result.stats is not None
    assert result.stats.get("extraction_method") == "pdfbox"
    assert result.stats.get("stat_block_profile") == "cof2"


@pytest.mark.skipif(not _clojure_available(), reason="Clojure CLI not available")
def test_run_clojure_import_rejects_low_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "reject.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from alembic import command
    from alembic.config import Config

    from rpg_core.storage import db as db_module

    db_module._engine = None
    cfg = Config("/workspace/alembic.ini")
    command.upgrade(cfg, "head")

    pdf_path = tmp_path / "tiny.pdf"
    _make_text_pdf(pdf_path, ["Too little text"])

    with pytest.raises(ClojureImportError, match="insufficient text coverage|rejected"):
        run_clojure_import(
            pdf_path,
            campaign_id="reject-test",
            game_system="cof2",
            db_path=db_path,
            coverage_threshold=0.3,
            timeout_s=600,
        )
