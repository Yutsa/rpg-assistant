from __future__ import annotations

import hashlib
import uuid
from pathlib import Path


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def document_id_from_hash(content_hash: str) -> str:
    return f"doc_{content_hash[:12]}"


def page_block_id(page_number: int, block_index: int) -> str:
    return f"block_{page_number:03d}_{block_index:03d}"


def chunk_id(page_start: int, index: int) -> str:
    return f"chunk_{page_start:03d}_{index:03d}"


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
