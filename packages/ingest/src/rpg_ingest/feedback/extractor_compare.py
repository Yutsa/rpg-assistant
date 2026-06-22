from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pymupdf

from rpg_core.models.raw import BBox
from rpg_ingest.raw.layout import blocks_from_raw_layout

_REPO_ROOT = Path(__file__).resolve().parents[5]
_INGEST_CLJ_DIR = _REPO_ROOT / "packages" / "ingest-clj"


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


def extract_pdfbox_raw_blocks(pdf_path: Path, page_number: int) -> dict[str, Any]:
    """PDFBox line-level blocks via the Clojure ingest CLI (no column heuristics)."""
    payload = _run_clojure_page_command(pdf_path, page_number, "extract-page")
    return _pdfbox_payload_to_page(
        payload,
        page_number=page_number,
        extraction_method="pdfbox_raw",
        block_id_prefix="pdfbox-raw",
    )


def extract_pdfbox_layout_blocks(pdf_path: Path, page_number: int) -> dict[str, Any]:
    """PDFBox blocks after column split, line merge and column-major ordering."""
    payload = _run_clojure_page_command(pdf_path, page_number, "extract-layout-page")
    return _pdfbox_payload_to_page(
        payload,
        page_number=page_number,
        extraction_method="pdfbox_layout",
        block_id_prefix="pdfbox-layout",
    )


def compare_page_extractors(pdf_path: Path, page_number: int) -> dict[str, Any]:
    pymupdf_page = extract_pymupdf_raw_blocks(pdf_path, page_number)
    pdfbox_raw_page = extract_pdfbox_raw_blocks(pdf_path, page_number)
    pdfbox_layout_page = extract_pdfbox_layout_blocks(pdf_path, page_number)
    width = pymupdf_page["width"] or pdfbox_raw_page["width"] or pdfbox_layout_page["width"]
    height = pymupdf_page["height"] or pdfbox_raw_page["height"] or pdfbox_layout_page["height"]
    return {
        "page_number": page_number,
        "width": width,
        "height": height,
        "pymupdf": pymupdf_page,
        "pdfbox": pdfbox_raw_page,
        "pdfbox_layout": pdfbox_layout_page,
    }
