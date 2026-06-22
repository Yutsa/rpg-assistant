from __future__ import annotations

import atexit
import json
import subprocess
import threading
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[5]
_INGEST_CLJ_DIR = _REPO_ROOT / "packages" / "ingest-clj"


class ClojurePdfboxSession:
    """Keeps a warm Clojure JVM alive for repeated page extractions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None

    def _start(self) -> None:
        if not _INGEST_CLJ_DIR.is_dir():
            raise FileNotFoundError(f"Clojure ingest module not found: {_INGEST_CLJ_DIR}")

        self._process = subprocess.Popen(
            ["clojure", "-M:ingest", "serve"],
            cwd=_INGEST_CLJ_DIR,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        assert self._process.stdout is not None
        ready_line = self._process.stdout.readline()
        if not ready_line:
            raise RuntimeError("Clojure serve process exited before ready signal")
        ready_payload = json.loads(ready_line)
        if not ready_payload.get("ready"):
            raise RuntimeError(f"Unexpected Clojure serve startup payload: {ready_line.strip()}")

    def _ensure_running(self) -> subprocess.Popen[str]:
        if self._process is None or self._process.poll() is not None:
            self._start()
        assert self._process is not None
        return self._process

    def extract_page(self, pdf_path: Path, page_number: int) -> dict[str, Any]:
        with self._lock:
            process = self._ensure_running()
            assert process.stdin is not None
            assert process.stdout is not None

            request = json.dumps(
                {"pdf": str(pdf_path.resolve()), "page": page_number},
                ensure_ascii=False,
            )
            process.stdin.write(f"{request}\n")
            process.stdin.flush()

            response_line = process.stdout.readline()
            if not response_line:
                raise RuntimeError("Clojure serve process closed stdout unexpectedly")

            payload = json.loads(response_line)
            if payload.get("error"):
                raise RuntimeError(str(payload["error"]))
            return payload

    def close(self) -> None:
        with self._lock:
            if self._process is None:
                return
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            self._process = None


_default_session = ClojurePdfboxSession()
atexit.register(_default_session.close)


def reset_clojure_pdfbox_session() -> None:
    """Test helper: restart the warm Clojure JVM."""
    _default_session.close()


def extract_pdfbox_page(pdf_path: Path, page_number: int) -> dict[str, Any]:
    return _default_session.extract_page(pdf_path, page_number)


def extract_pdfbox_document(pdf_path: Path) -> dict[str, Any]:
    if not _INGEST_CLJ_DIR.is_dir():
        raise FileNotFoundError(f"Clojure ingest module not found: {_INGEST_CLJ_DIR}")

    command = [
        "clojure",
        "-M:ingest",
        "raw",
        "extract-document",
        "--pdf",
        str(pdf_path.resolve()),
    ]
    completed = subprocess.run(
        command,
        cwd=_INGEST_CLJ_DIR,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "Clojure extract-document failed"
        raise RuntimeError(message)

    payload = json.loads(completed.stdout)
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    return payload
