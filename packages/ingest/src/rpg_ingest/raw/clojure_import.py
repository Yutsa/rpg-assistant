from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rpg_ingest.raw.clojure_runtime import INGEST_CLJ_DIR, clojure_subprocess_env

_TERMINAL_FAILURE_STATUSES = frozenset({"failed", "rejected"})


@dataclass(frozen=True)
class ClojureImportResult:
    ingestion_run_id: str
    campaign_id: str
    document_id: str | None
    status: str
    stats: dict[str, Any] | None = None
    error_message: str | None = None


class ClojureImportError(RuntimeError):
    """Raised when the Clojure import CLI fails or returns a terminal error status."""

    def __init__(self, message: str, *, result: ClojureImportResult | None = None) -> None:
        super().__init__(message)
        self.result = result


def run_clojure_import(
    pdf_path: Path,
    *,
    campaign_id: str,
    campaign_title: str = "",
    game_system: str = "cof2",
    db_path: Path | None = None,
    coverage_threshold: float = 0.3,
    reimport: bool = True,
    timeout_s: int = 600,
) -> ClojureImportResult:
    """Run `clojure -M:ingest import` and parse the JSON result from stdout."""
    if not INGEST_CLJ_DIR.is_dir():
        raise FileNotFoundError(f"Clojure ingest module not found: {INGEST_CLJ_DIR}")

    resolved_pdf = pdf_path.resolve()
    command = [
        "clojure",
        "-M:ingest",
        "import",
        "--pdf",
        str(resolved_pdf),
        "--campaign-id",
        campaign_id,
        "--game-system",
        game_system,
        "--coverage-threshold",
        str(coverage_threshold),
    ]
    if campaign_title:
        command.extend(["--campaign-title", campaign_title])
    if db_path is not None:
        command.extend(["--db", str(db_path.resolve())])
    if not reimport:
        command.append("--no-reimport")

    completed = subprocess.run(
        command,
        cwd=INGEST_CLJ_DIR,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_s,
        env=clojure_subprocess_env(),
    )

    payload = _parse_cli_json(completed.stdout)
    if payload.get("error"):
        raise ClojureImportError(str(payload["error"]))

    if completed.returncode != 0 and not payload:
        message = completed.stderr.strip() or completed.stdout.strip() or "Clojure import failed"
        raise ClojureImportError(message)

    result = _result_from_payload(payload)
    if result.status in _TERMINAL_FAILURE_STATUSES:
        detail = result.error_message or f"Clojure import {result.status}"
        raise ClojureImportError(detail, result=result)
    return result


def _parse_cli_json(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _result_from_payload(payload: dict[str, Any]) -> ClojureImportResult:
    return ClojureImportResult(
        ingestion_run_id=str(payload.get("ingestion_run_id", "")),
        campaign_id=str(payload.get("campaign_id", "")),
        document_id=payload.get("document_id"),
        status=str(payload.get("status", "")),
        stats=payload.get("stats"),
        error_message=payload.get("error_message"),
    )
