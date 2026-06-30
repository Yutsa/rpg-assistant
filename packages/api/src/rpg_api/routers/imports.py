from __future__ import annotations

import os
import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.engine import make_url

from rpg_api.deps import get_raw_repo
from rpg_api.errors import ApiError, bad_request, not_found
from rpg_api.schemas import GameSystemOut, ImportCreateOut, IngestionRunOut
from rpg_core.models.raw import IngestionRunRecord
from rpg_core.storage.db import get_database_url
from rpg_core.storage.ids import new_id
from rpg_core.storage.repositories.raw import RawRepository
from rpg_ingest.raw.clojure_import import ClojureImportError, run_clojure_import
from rpg_ingest.raw.stat_blocks import list_importable_game_systems, known_game_system_ids

router = APIRouter(tags=["imports"])

_CAMPAIGN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_DEFAULT_UPLOAD_DIR = Path("data/uploads")
_DEFAULT_MAX_UPLOAD_MB = 50
_DEFAULT_IMPORT_TIMEOUT_S = 600

_pending_lock = threading.Lock()
_pending_imports: dict[str, _PendingImport] = {}
_run_aliases: dict[str, str] = {}


@dataclass
class _PendingImport:
    campaign_id: str
    real_run_id: str | None = None
    error_message: str | None = None
    done: bool = False
    result_status: str | None = None


def _upload_dir() -> Path:
    configured = os.environ.get("RPG_UPLOAD_DIR", "").strip()
    path = Path(configured) if configured else _DEFAULT_UPLOAD_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _max_upload_bytes() -> int:
    raw = os.environ.get("RPG_MAX_UPLOAD_MB", str(_DEFAULT_MAX_UPLOAD_MB)).strip()
    try:
        mb = int(raw)
    except ValueError:
        mb = _DEFAULT_MAX_UPLOAD_MB
    return max(1, mb) * 1024 * 1024


def _import_timeout_s() -> int:
    raw = os.environ.get("RPG_IMPORT_TIMEOUT_S", str(_DEFAULT_IMPORT_TIMEOUT_S)).strip()
    try:
        return max(60, int(raw))
    except ValueError:
        return _DEFAULT_IMPORT_TIMEOUT_S


def _default_db_path() -> Path | None:
    url = make_url(get_database_url())
    if not url.drivername.startswith("sqlite"):
        return None
    database = url.database
    if not database or database == ":memory:":
        return None
    return Path(database).resolve()


def _sanitize_filename(name: str) -> str:
    base = Path(name).name or "upload.pdf"
    safe = re.sub(r"[^\w.\-]", "_", base)
    return safe if safe.lower().endswith(".pdf") else f"{safe}.pdf"


def _ingestion_run_out(record: IngestionRunRecord) -> IngestionRunOut:
    return IngestionRunOut(
        id=record.id,
        campaign_id=record.campaign_id,
        document_id=record.document_id,
        status=record.status,
        stage=record.stage,
        stats=record.stats or None,
        error_message=record.error_message,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


def _resolve_run_id(ingestion_run_id: str) -> str:
    with _pending_lock:
        return _run_aliases.get(ingestion_run_id, ingestion_run_id)


@router.get("/ingestion/game-systems", response_model=list[GameSystemOut])
def list_game_systems() -> list[GameSystemOut]:
    return [
        GameSystemOut(
            id=entry.id,
            label=entry.label,
            description=entry.description,
            supports_stat_blocks=entry.supports_stat_blocks,
            default=entry.default,
        )
        for entry in list_importable_game_systems()
    ]


@router.post("/imports", status_code=202, response_model=ImportCreateOut)
async def create_import(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    campaign_id: str = Form(...),
    campaign_title: str = Form(""),
    game_system: str = Form("cof2"),
    reimport: bool = Form(True),
) -> JSONResponse:
    normalized_campaign_id = campaign_id.strip()
    if normalized_campaign_id != normalized_campaign_id.lower():
        raise bad_request("campaign_id must be a lowercase slug")
    if not _CAMPAIGN_ID_RE.fullmatch(normalized_campaign_id):
        raise bad_request(
            "campaign_id must match ^[a-z0-9][a-z0-9_-]{0,63}$ "
            "(lowercase slug, e.g. momie or ma-campagne)"
        )

    normalized_game_system = game_system.strip().lower()
    if normalized_game_system not in known_game_system_ids():
        allowed = ", ".join(sorted(known_game_system_ids()))
        raise ApiError(
            422,
            f"Unknown game_system: {game_system!r}. Allowed values: {allowed}",
            code="invalid_game_system",
        )

    filename = file.filename or ""
    content_type = (file.content_type or "").lower()
    if not filename.lower().endswith(".pdf") and content_type not in {
        "application/pdf",
        "application/x-pdf",
    }:
        raise bad_request("Uploaded file must be a PDF")

    payload = await file.read()
    if not payload:
        raise bad_request("Uploaded file is empty")
    if len(payload) > _max_upload_bytes():
        raise bad_request(f"PDF exceeds maximum upload size ({_max_upload_bytes() // (1024 * 1024)} MB)")

    upload_path = _upload_dir() / f"{uuid.uuid4().hex}_{_sanitize_filename(filename)}"
    upload_path.write_bytes(payload)

    tracking_id = new_id("run")
    with _pending_lock:
        _pending_imports[tracking_id] = _PendingImport(campaign_id=normalized_campaign_id)

    background_tasks.add_task(
        _background_import,
        tracking_id=tracking_id,
        pdf_path=upload_path,
        campaign_id=normalized_campaign_id,
        campaign_title=campaign_title.strip() or normalized_campaign_id,
        game_system=normalized_game_system,
        reimport=reimport,
    )

    body = ImportCreateOut(
        ingestion_run_id=tracking_id,
        campaign_id=normalized_campaign_id,
        status="running",
    )
    return JSONResponse(status_code=202, content=body.model_dump())


@router.get("/ingestion-runs/{ingestion_run_id}", response_model=IngestionRunOut)
def get_ingestion_run(
    ingestion_run_id: str,
    repo: RawRepository = Depends(get_raw_repo),
) -> IngestionRunOut:
    real_id = _resolve_run_id(ingestion_run_id)
    record = repo.get_ingestion_run(real_id)
    if record is not None:
        return _ingestion_run_out(record)

    with _pending_lock:
        pending = _pending_imports.get(ingestion_run_id)

    if pending is None:
        raise not_found(f"Unknown ingestion_run_id: {ingestion_run_id}")

    if pending.error_message and pending.done:
        return IngestionRunOut(
            id=ingestion_run_id,
            campaign_id=pending.campaign_id,
            status=pending.result_status or "failed",
            stage="raw",
            error_message=pending.error_message,
        )

    return IngestionRunOut(
        id=ingestion_run_id,
        campaign_id=pending.campaign_id,
        status="running",
        stage="raw",
    )


def _background_import(
    *,
    tracking_id: str,
    pdf_path: Path,
    campaign_id: str,
    campaign_title: str,
    game_system: str,
    reimport: bool,
) -> None:
    try:
        result = run_clojure_import(
            pdf_path,
            campaign_id=campaign_id,
            campaign_title=campaign_title,
            game_system=game_system,
            db_path=_default_db_path(),
            reimport=reimport,
            timeout_s=_import_timeout_s(),
        )
        with _pending_lock:
            _run_aliases[tracking_id] = result.ingestion_run_id
            pending = _pending_imports[tracking_id]
            pending.real_run_id = result.ingestion_run_id
            pending.done = True
            pending.result_status = result.status
    except ClojureImportError as exc:
        with _pending_lock:
            pending = _pending_imports[tracking_id]
            pending.done = True
            pending.error_message = str(exc)
            if exc.result is not None:
                _run_aliases[tracking_id] = exc.result.ingestion_run_id
                pending.real_run_id = exc.result.ingestion_run_id
                pending.result_status = exc.result.status
            else:
                pending.result_status = "failed"
    except Exception as exc:
        with _pending_lock:
            pending = _pending_imports[tracking_id]
            pending.done = True
            pending.error_message = str(exc)
            pending.result_status = "failed"
