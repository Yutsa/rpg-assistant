#!/usr/bin/env python3
"""Generic COF2 campaign ingestion audit (orphan blocks, chunks, stat blocks)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pymupdf

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_core.storage.db import get_connection
from rpg_core.storage.ids import page_block_id
from rpg_core.storage.repositories.raw import RawRepository
from rpg_ingest.raw.importer import run as import_pdf
from rpg_ingest.raw.layout import extract_layout_pages
from rpg_ingest.raw.block_merging import merge_drop_caps, merge_fragmented_blocks
from rpg_ingest.raw.filtering import filter_watermark_blocks
from rpg_ingest.raw.sections import detect_sections
from rpg_ingest.raw.chunking import build_chunks, chunk_uniqueness_stats
from rpg_ingest.raw.stat_blocks import annotate_stat_blocks, resolve_profile

CREDITS_MARKERS = ("Black Book", "Tous droits réservés", "ISBN")
EDITORIAL_RE = re.compile(
    r"(ISBN|BBECOF\d+|Prix\s*:|\bedouard\.willisseck@gmail\.com\b)",
    re.IGNORECASE,
)


@dataclass
class Finding:
    campaign_id: str
    document_id: str
    category: str
    severity: str
    message: str
    details: dict = field(default_factory=dict)


def _referenced_block_ids(chunks) -> set[str]:
    return {
        block_id
        for chunk in chunks
        for span in chunk.source_spans
        for block_id in span.page_block_ids
    }


def _chunk_page_gaps(chunks) -> list[dict]:
    gaps: list[dict] = []
    for chunk in chunks:
        pages = sorted({span.page for span in chunk.source_spans})
        for prev, nxt in zip(pages, pages[1:]):
            if nxt > prev + 1:
                gaps.append(
                    {
                        "chunk_id": chunk.id,
                        "from_page": prev,
                        "to_page": nxt,
                        "missing": list(range(prev + 1, nxt)),
                    }
                )
    return gaps


def _credits_in_non_credits_chunks(chunks, sections) -> list[dict]:
    issues: list[dict] = []
    credits_section_ids = {
        s.id for s in sections if s.title.strip().upper() == "CRÉDITS"
    }
    intro_markers = ("aventure pour", "groupe de", "il est nécessaire", "épisode du cycle")
    for chunk in chunks:
        if chunk.section_id in credits_section_ids:
            continue
        text_lower = chunk.text.lower()
        has_credits = any(m.lower() in text_lower for m in CREDITS_MARKERS)
        has_intro = any(m in text_lower for m in intro_markers)
        if has_credits and has_intro:
            section = next(
                (s for s in sections if s.id == chunk.section_id), None
            )
            issues.append(
                {
                    "chunk_id": chunk.id,
                    "section": section.title if section else None,
                    "pages": (chunk.page_start, chunk.page_end),
                }
            )
    return issues


def _truncated_all_caps_sections(sections) -> list[str]:
    truncated: list[str] = []
    for section in sections:
        title = section.title.replace("\n", " ").strip()
        if title.isupper() and len(title.split()) <= 4 and len(title) < 25:
            if not any(
                other.title.replace("\n", " ").startswith(title + " ")
                for other in sections
                if other.id != section.id
            ):
                truncated.append(title)
    return truncated


def _stat_block_issues(chunks) -> list[dict]:
    issues: list[dict] = []
    for chunk in chunks:
        if chunk.chunk_type_hint != "stat_block":
            continue
        stat = chunk.metadata.get("stat_block") or {}
        name = stat.get("name") or "?"
        abilities = stat.get("abilities") or []
        raw = chunk.text
        inline_caps = re.findall(
            r"(?<![A-Za-zÀ-ÿ])([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜŸÇ0-9\s\-'\u2019]{2,}?)\s*(?:\([A-Z]\))?\s*:",
            raw,
        )
        parsed_titles = {a.get("title", "") for a in abilities}
        missing = [
            cap.strip()
            for cap in inline_caps
            if cap.strip() not in parsed_titles
            and cap.strip().upper()
            not in {"AGI", "FOR", "CON", "INT", "PER", "CHA", "VOL", "DEF", "PV", "NC"}
            and not cap.strip().startswith("VOIE")
        ]
        if missing:
            issues.append(
                {
                    "chunk_id": chunk.id,
                    "name": name,
                    "missing_abilities": missing[:10],
                    "parsed": list(parsed_titles),
                }
            )
    return issues


def audit_document(
    *,
    campaign_id: str,
    document_id: str,
    pdf_path: Path,
) -> list[Finding]:
    findings: list[Finding] = []
    with get_connection() as conn:
        repo = RawRepository(conn)
        sections = repo.list_sections(document_id)
        chunks = repo.list_chunks(document_id, limit=500)

    document = pymupdf.open(pdf_path)
    pages = extract_layout_pages(document)
    profile = resolve_profile("cof2", pages)
    pages = filter_watermark_blocks(pages).pages
    pages = merge_fragmented_blocks(pages, profile=profile).pages
    pages = merge_drop_caps(pages).pages
    stat_result = annotate_stat_blocks(pages, profile)
    pages = stat_result.pages
    section_result = detect_sections(
        pages,
        campaign_id=campaign_id,
        document_id=document_id,
        profile=profile,
    )
    pipeline_chunks = build_chunks(
        pages,
        section_result.sections,
        campaign_id=campaign_id,
        document_id=document_id,
        heading_anchors=section_result.heading_anchors,
        content_only_section_ids=section_result.content_only_section_ids,
        stat_spans=stat_result.spans,
        profile=profile,
    )

    content_only_anchors = {
        anchor
        for section, anchor in zip(
            section_result.sections,
            section_result.heading_anchors,
            strict=True,
        )
        if section.id in section_result.content_only_section_ids
    }
    heading_positions = set(section_result.heading_anchors) - content_only_anchors
    content_block_ids = {
        page_block_id(document_id, page.page_number, block.block_index)
        for page in pages
        for block in page.blocks
        if (page.page_number, block.block_index) not in heading_positions
    }
    referenced = _referenced_block_ids(pipeline_chunks)
    orphans = content_block_ids - referenced
    if orphans:
        findings.append(
            Finding(
                campaign_id=campaign_id,
                document_id=document_id,
                category="orphan_blocks",
                severity="major" if len(orphans) > 3 else "minor",
                message=f"{len(orphans)} content block(s) not referenced by any chunk",
                details={"sample_block_ids": sorted(orphans)[:15]},
            )
        )

    uniqueness = chunk_uniqueness_stats(pipeline_chunks)
    if uniqueness["duplicate_chunk_count"] > 1:
        findings.append(
            Finding(
                campaign_id=campaign_id,
                document_id=document_id,
                category="duplicate_chunks",
                severity="major",
                message="Duplicate chunk signatures detected",
                details=dict(uniqueness),
            )
        )

    for gap in _chunk_page_gaps(chunks):
        findings.append(
            Finding(
                campaign_id=campaign_id,
                document_id=document_id,
                category="page_gap",
                severity="major",
                message=f"Chunk skips page(s) {gap['missing']}",
                details=gap,
            )
        )

    for issue in _credits_in_non_credits_chunks(chunks, sections):
        findings.append(
            Finding(
                campaign_id=campaign_id,
                document_id=document_id,
                category="credits_mixing",
                severity="major",
                message="Chunk mixes editorial credits with intro narrative",
                details=issue,
            )
        )

    for title in _truncated_all_caps_sections(sections):
        if any(
            f.category == "truncated_title" and f.details.get("title") == title
            for f in findings
        ):
            continue
        findings.append(
            Finding(
                campaign_id=campaign_id,
                document_id=document_id,
                category="truncated_title",
                severity="minor",
                message=f"Possibly truncated section title: {title!r}",
                details={"title": title},
            )
        )

    for issue in _stat_block_issues(chunks):
        findings.append(
            Finding(
                campaign_id=campaign_id,
                document_id=document_id,
                category="stat_block_abilities",
                severity="major",
                message=f"Stat block {issue['name']!r} may have unparsed abilities",
                details=issue,
            )
        )

    # Sections with no chunks
    section_ids_with_chunks = {c.section_id for c in chunks if c.section_id}
    empty_sections = [
        s.title for s in sections if s.id not in section_ids_with_chunks
    ]
    if empty_sections:
        findings.append(
            Finding(
                campaign_id=campaign_id,
                document_id=document_id,
                category="empty_sections",
                severity="minor",
                message=f"{len(empty_sections)} section(s) have no chunks",
                details={"titles": empty_sections[:20]},
            )
        )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_id")
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("--title", default="")
    parser.add_argument("--skip-import", action="store_true")
    parser.add_argument("--document-id", default="")
    args = parser.parse_args()

    pdf_path = args.pdf_path.resolve()
    if not args.skip_import:
        result = import_pdf(
            pdf_path,
            campaign_id=args.campaign_id,
            campaign_title=args.title or args.campaign_id,
            game_system="cof2",
        )
        if result.status != "completed":
            print(json.dumps({"status": result.status, "error": result.error_message}))
            return 1
        document_id = result.document_id
    else:
        document_id = args.document_id
        if not document_id:
            parser.error("--document-id required with --skip-import")

    findings = audit_document(
        campaign_id=args.campaign_id,
        document_id=document_id,
        pdf_path=pdf_path,
    )
    report = {
        "campaign_id": args.campaign_id,
        "document_id": document_id,
        "pdf_path": str(pdf_path),
        "finding_count": len(findings),
        "findings": [asdict(f) for f in findings],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
