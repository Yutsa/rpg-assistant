from __future__ import annotations

import json
import subprocess
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pymupdf

from rpg_core.models.raw import BBox, PageBlockRecord
from rpg_core.storage.repositories.raw import RawRepository
from rpg_ingest.raw.clojure_pdfbox import extract_pdfbox_page, reset_clojure_pdfbox_session
from rpg_ingest.raw.extractor_compare_ingest import (
    COMPARE_LANE_PDFBOX,
    COMPARE_LANE_PYMUPDF,
)
from rpg_ingest.raw.layout import blocks_from_raw_layout

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


def clear_compare_cache() -> None:
    """Test helper: drop cached page comparisons."""
    with _compare_cache_lock:
        _compare_cache.clear()


_compare_cache: OrderedDict[tuple[str, float, int], dict[str, Any]] = OrderedDict()
_compare_cache_lock = threading.Lock()


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


def _page_block_record_to_dict(
    block: PageBlockRecord,
    *,
    block_id_prefix: str,
) -> dict[str, Any]:
    lane = (block.metadata or {}).get("compare_lane", block_id_prefix)
    return _block_to_dict(
        block_id=block.id,
        page_number=block.page_number,
        block_index=block.block_index,
        text=block.text,
        bbox=block.bbox,
        metadata={**block.metadata, "compare_lane": lane},
    )


def _lane_page_from_blocks(
    *,
    page_number: int,
    width: float,
    height: float,
    extraction_method: str,
    block_id_prefix: str,
    blocks: list[PageBlockRecord],
) -> dict[str, Any]:
    sorted_blocks = sorted(blocks, key=lambda block: block.block_index)
    return {
        "page_number": page_number,
        "width": width,
        "height": height,
        "extraction_method": extraction_method,
        "blocks": [
            _page_block_record_to_dict(block, block_id_prefix=block_id_prefix)
            for block in sorted_blocks
        ],
    }


def compare_page_extractors_from_db(
    repo: RawRepository,
    document_id: str,
    page_number: int,
) -> dict[str, Any] | None:
    page = repo.get_page(document_id, page_number)
    if page is None or page.width is None or page.height is None:
        return None

    blocks = repo.list_page_blocks_for_page(document_id, page_number)
    lanes: dict[str, list[PageBlockRecord]] = {
        COMPARE_LANE_PYMUPDF: [],
        COMPARE_LANE_PDFBOX: [],
    }
    for block in blocks:
        lane = (block.metadata or {}).get("compare_lane")
        if lane in lanes:
            lanes[lane].append(block)

    if not lanes[COMPARE_LANE_PYMUPDF] or not lanes[COMPARE_LANE_PDFBOX]:
        return None

    return {
        "page_number": page_number,
        "width": float(page.width),
        "height": float(page.height),
        "pymupdf": _lane_page_from_blocks(
            page_number=page_number,
            width=float(page.width),
            height=float(page.height),
            extraction_method="pymupdf_raw",
            block_id_prefix=COMPARE_LANE_PYMUPDF,
            blocks=lanes[COMPARE_LANE_PYMUPDF],
        ),
        "pdfbox": _lane_page_from_blocks(
            page_number=page_number,
            width=float(page.width),
            height=float(page.height),
            extraction_method="pdfbox",
            block_id_prefix=COMPARE_LANE_PDFBOX,
            blocks=lanes[COMPARE_LANE_PDFBOX],
        ),
        "source": "database",
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
    payload = extract_pdfbox_page(pdf_path, page_number)
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
        "source": "live",
    }


def compare_page_extractors(
    pdf_path: Path,
    page_number: int,
    *,
    repo: RawRepository | None = None,
    document_id: str | None = None,
) -> dict[str, Any]:
    if repo is not None and document_id is not None:
        db_result = compare_page_extractors_from_db(repo, document_id, page_number)
        if db_result is not None:
            return db_result

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


def _run_clojure_page_command(pdf_path: Path, page_number: int, action: str) -> dict[str, Any]:
    """Backward-compatible helper for tests invoking the Clojure CLI directly."""
    clj_root = Path(__file__).resolve().parents[4] / "ingest-clj"
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
        cwd=clj_root,
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
