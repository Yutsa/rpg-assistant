from __future__ import annotations

import atexit
import json
import subprocess
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pymupdf

from rpg_core.models.raw import BBox
from rpg_ingest.raw.layout import blocks_from_raw_layout

_REPO_ROOT = Path(__file__).resolve().parents[5]
_INGEST_CLJ_DIR = _REPO_ROOT / "packages" / "ingest-clj"
_COMPARE_CACHE_MAX = 64


def _block_to_dict(
    *,
    block_id: str,
    page_number: int,
    block_index: int,
    text: str,
    bbox: BBox,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": block_id,
        "page_number": page_number,
        "block_index": block_index,
        "text": text,
        "bbox": bbox.model_dump(),
        "metadata": metadata,
    }


class _ClojurePdfboxSession:
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
            stderr=subprocess.PIPE,
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
                stderr = ""
                if process.stderr is not None:
                    stderr = process.stderr.read()
                raise RuntimeError(
                    f"Clojure serve process closed stdout unexpectedly: {stderr.strip()}"
                )

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


_clojure_session = _ClojurePdfboxSession()
atexit.register(_clojure_session.close)
_compare_cache: OrderedDict[tuple[str, float, int], dict[str, Any]] = OrderedDict()
_compare_cache_lock = threading.Lock()


def reset_clojure_pdfbox_session() -> None:
    """Test helper: restart the warm Clojure JVM."""
    _clojure_session.close()


def clear_compare_cache() -> None:
    """Test helper: drop cached page comparisons."""
    with _compare_cache_lock:
        _compare_cache.clear()


def _run_clojure_page_command(pdf_path: Path, page_number: int, action: str) -> dict[str, Any]:
    if not _INGEST_CLJ_DIR.is_dir():
        raise FileNotFoundError(f"Clojure ingest module not found: {_INGEST_CLJ_DIR}")

    command = [
        "clojure",
        "-M:ingest",
        "raw",
        action,
        "--pdf",
        str(pdf_path.resolve()),
        "--page",
        str(page_number),
    ]
    completed = subprocess.run(
        command,
        cwd=_INGEST_CLJ_DIR,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or f"Clojure {action} failed"
        raise RuntimeError(message)

    payload = json.loads(completed.stdout)
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    return payload


def _pdfbox_payload_to_page(
    payload: dict[str, Any],
    *,
    page_number: int,
    extraction_method: str,
    block_id_prefix: str,
) -> dict[str, Any]:
    blocks = []
    for block in payload.get("blocks") or []:
        bbox = block.get("bbox") or {}
        block_index = int(block.get("block_index", 0))
        blocks.append(
            _block_to_dict(
                block_id=f"{block_id_prefix}-{page_number}-{block_index}",
                page_number=page_number,
                block_index=block_index,
                text=str(block.get("text") or ""),
                bbox=BBox(
                    x0=float(bbox.get("x0", 0)),
                    y0=float(bbox.get("y0", 0)),
                    x1=float(bbox.get("x1", 0)),
                    y1=float(bbox.get("y1", 0)),
                ),
                metadata=dict(block.get("metadata") or {}),
            )
        )

    return {
        "page_number": int(payload.get("page_number", page_number)),
        "width": float(payload.get("width", 0)),
        "height": float(payload.get("height", 0)),
        "extraction_method": extraction_method,
        "blocks": blocks,
    }


def extract_pymupdf_raw_blocks(pdf_path: Path, page_number: int) -> dict[str, Any]:
    """PyMuPDF page.get_text('dict') blocks without post-processing."""
    with pymupdf.open(pdf_path) as document:
        if page_number < 1 or page_number > document.page_count:
            raise ValueError(
                f"Page {page_number} out of range (document has {document.page_count} pages)"
            )
        page = document[page_number - 1]
        rect = page.rect
        raw_layout = page.get_text("dict")
        blocks = blocks_from_raw_layout(raw_layout, page_number)
        return {
            "page_number": page_number,
            "width": rect.width,
            "height": rect.height,
            "extraction_method": "pymupdf_raw",
            "blocks": [
                _block_to_dict(
                    block_id=f"pymupdf-{page_number}-{block.block_index}",
                    page_number=page_number,
                    block_index=block.block_index,
                    text=block.text,
                    bbox=block.bbox,
                    metadata=block.metadata,
                )
                for block in blocks
            ],
        }


def extract_pdfbox_blocks(pdf_path: Path, page_number: int) -> dict[str, Any]:
    """PDFBox blocks via the warm Clojure ingest JVM."""
    payload = _clojure_session.extract_page(pdf_path, page_number)
    return _pdfbox_payload_to_page(
        payload,
        page_number=page_number,
        extraction_method="pdfbox",
        block_id_prefix="pdfbox",
    )


def _compare_page_extractors_uncached(pdf_path: Path, page_number: int) -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=2) as executor:
        pymupdf_future = executor.submit(extract_pymupdf_raw_blocks, pdf_path, page_number)
        pdfbox_future = executor.submit(extract_pdfbox_blocks, pdf_path, page_number)
        pymupdf_page = pymupdf_future.result()
        pdfbox_page = pdfbox_future.result()

    width = pymupdf_page["width"] or pdfbox_page["width"]
    height = pymupdf_page["height"] or pdfbox_page["height"]
    return {
        "page_number": page_number,
        "width": width,
        "height": height,
        "pymupdf": pymupdf_page,
        "pdfbox": pdfbox_page,
    }


def compare_page_extractors(pdf_path: Path, page_number: int) -> dict[str, Any]:
    resolved = pdf_path.resolve()
    cache_key = (str(resolved), resolved.stat().st_mtime, page_number)
    with _compare_cache_lock:
        cached = _compare_cache.get(cache_key)
        if cached is not None:
            _compare_cache.move_to_end(cache_key)
            return cached

    result = _compare_page_extractors_uncached(resolved, page_number)
    with _compare_cache_lock:
        _compare_cache[cache_key] = result
        _compare_cache.move_to_end(cache_key)
        while len(_compare_cache) > _COMPARE_CACHE_MAX:
            _compare_cache.popitem(last=False)
    return result
