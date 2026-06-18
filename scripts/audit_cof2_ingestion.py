#!/usr/bin/env python3
"""Import COF2 PDFs and verify ingestion against the audit checklist."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rpg_core.storage.db import get_connection
from rpg_core.storage.repositories.raw import RawRepository
from rpg_ingest.raw.importer import run as import_pdf
from tests.fixtures.cof2_audit_expectations import (
    CENTAURE_ABILITIES,
    FEE_ABILITIES,
    FAELYS_CREDITS_MARKERS,
    FAELYS_CREDITS_SECTION,
    FAELYS_IMPLICATION_SECTION,
    FAELYS_INTRO_MARKERS,
    FAELYS_INTRO_SECTION,
    FAELYS_SHADOW_BOX_TITLE,
    FAELYS_SHADOW_BOX_TRUNCATED,
    FAELYS_ZONE_TITLES,
    MOMIE_CREDITS_MARKERS,
    MOMIE_SYNOPSIS_MARKERS,
    MOMIE_SYNOPSIS_SECTION,
    SOMBRE_FEE_ABILITIES,
)
from tests.fixtures.pipeline import contains_any, section_by_title, stat_block_ability_titles

DEFAULT_MOMIE_PDF = Path(
    "/home/edouard/Téléchargements/COF2_10_Mondanites_Et_Momies_web_v1a.pdf"
)
DEFAULT_FAELYS_PDF = Path(
    "/home/edouard/Téléchargements/COF2_07_Le_Dernier_Faelys_web_v0.pdf"
)
FALLBACK_DIRS = (
    REPO_ROOT / "data" / "pdfs",
    Path("/home/edouard/Téléchargements"),
)


@dataclass
class Finding:
    document: str
    issue_id: int
    severity: str
    message: str
    details: dict = field(default_factory=dict)


def resolve_pdf(path: Path, *, glob_pattern: str) -> Path:
    if path.is_file():
        return path
    for directory in FALLBACK_DIRS:
        matches = sorted(directory.glob(glob_pattern))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"PDF not found: {path}")


def chunk_texts_for_section_title(
    repo: RawRepository, document_id: str, title: str
) -> list[str]:
    sections = repo.list_sections(document_id)
    section = section_by_title(sections, title)
    chunks = repo.list_chunks(document_id, section_id=section.id, limit=500)
    return [chunk.text for chunk in chunks]


def section_parent_title(
    repo: RawRepository, document_id: str, section_title: str
) -> str | None:
    sections = repo.list_sections(document_id)
    section = section_by_title(sections, section_title)
    if not section.parent_section_id:
        return None
    parent = next(
        (candidate for candidate in sections if candidate.id == section.parent_section_id),
        None,
    )
    return parent.title if parent else None


def audit_momie(repo: RawRepository, document_id: str) -> list[Finding]:
    findings: list[Finding] = []
    synopsis_text = " ".join(
        chunk_texts_for_section_title(repo, document_id, MOMIE_SYNOPSIS_SECTION)
    )
    if not contains_any(synopsis_text, MOMIE_SYNOPSIS_MARKERS):
        findings.append(
            Finding(
                document="momie",
                issue_id=1,
                severity="major",
                message="Synopsis markers missing from intro section",
            )
        )
    if contains_any(synopsis_text, MOMIE_CREDITS_MARKERS):
        findings.append(
            Finding(
                document="momie",
                issue_id=1,
                severity="major",
                message="Editorial credits still present in synopsis chunk",
            )
        )
    return findings


def audit_faelys(repo: RawRepository, document_id: str) -> list[Finding]:
    findings: list[Finding] = []
    sections = repo.list_sections(document_id)
    titles = [section.title for section in sections]

    credits_text = " ".join(
        chunk_texts_for_section_title(repo, document_id, FAELYS_CREDITS_SECTION)
    )
    intro_text = " ".join(
        chunk_texts_for_section_title(repo, document_id, FAELYS_INTRO_SECTION)
    )
    if contains_any(credits_text, FAELYS_INTRO_MARKERS):
        findings.append(
            Finding(
                document="faelys",
                issue_id=2,
                severity="major",
                message="Credits chunk still contains intro narrative",
            )
        )
    if contains_any(intro_text, FAELYS_CREDITS_MARKERS):
        findings.append(
            Finding(
                document="faelys",
                issue_id=2,
                severity="major",
                message="Intro chunk still contains editorial credits",
            )
        )

    if FAELYS_SHADOW_BOX_TITLE not in titles and FAELYS_SHADOW_BOX_TRUNCATED in titles:
        findings.append(
            Finding(
                document="faelys",
                issue_id=3,
                severity="major",
                message="Shadow-box title truncated across sections",
                details={"titles": titles},
            )
        )

    implication_parent = section_parent_title(
        repo, document_id, FAELYS_ZONE_TITLES[0]
    )
    if implication_parent == FAELYS_IMPLICATION_SECTION:
        findings.append(
            Finding(
                document="faelys",
                issue_id=4,
                severity="major",
                message=f"Zone section still child of {FAELYS_IMPLICATION_SECTION!r}",
                details={"zone": FAELYS_ZONE_TITLES[0]},
            )
        )

    chunks = repo.list_chunks(document_id, limit=500)
    palace_chunks = [
        chunk
        for chunk in chunks
        if chunk.page_start <= 10 <= chunk.page_end and chunk.page_end >= 12
    ]
    for chunk in palace_chunks:
        if chunk.page_start <= 10 and chunk.page_end >= 12 and 11 not in range(
            chunk.page_start, chunk.page_end + 1
        ):
            if "palais" in chunk.text.lower() or "epitialm" in chunk.text.lower():
                findings.append(
                    Finding(
                        document="faelys",
                        issue_id=8,
                        severity="major",
                        message="Palace chunk skips page 11",
                        details={"chunk_id": chunk.id, "pages": (chunk.page_start, chunk.page_end)},
                    )
                )

    mille_chunks = [
        chunk
        for chunk in chunks
        if "mille-pattes" in chunk.text.lower() or "mille pattes" in chunk.text.lower()
    ]
    if len(mille_chunks) > 1:
        orphan = [
            chunk
            for chunk in mille_chunks
            if chunk.chunk_type_hint != "stat_block" and len(chunk.text) < 40
        ]
        if orphan:
            findings.append(
                Finding(
                    document="faelys",
                    issue_id=9,
                    severity="minor",
                    message="MILLE-PATTES stat block split with orphan fragment",
                    details={"chunk_ids": [chunk.id for chunk in orphan]},
                )
            )

    centaures_text = " ".join(
        chunk_texts_for_section_title(repo, document_id, "Les centaures")
    )
    champs_text = " ".join(
        chunk_texts_for_section_title(repo, document_id, "Les champs repoussés")
    )
    if "centaure" in champs_text.lower() and len(champs_text) > 200:
        findings.append(
            Finding(
                document="faelys",
                issue_id=10,
                severity="major",
                message="Centaure narrative text assigned to Les champs repoussés",
            )
        )
    if "homade" not in centaures_text.lower() and "centaure" not in centaures_text.lower():
        findings.append(
            Finding(
                document="faelys",
                issue_id=10,
                severity="minor",
                message="Les centaures section missing expected narrative",
            )
        )

    for name, expected in (
        ("CENTAURE", CENTAURE_ABILITIES),
        ("FÉE", FEE_ABILITIES),
        ("SOMBRE FÉE", SOMBRE_FEE_ABILITIES),
    ):
        try:
            titles = stat_block_ability_titles(chunks, name)
        except AssertionError:
            continue
        missing = [ability for ability in expected if ability not in titles]
        if missing:
            findings.append(
                Finding(
                    document="faelys",
                    issue_id={"CENTAURE": 5, "FÉE": 6, "SOMBRE FÉE": 7}[name],
                    severity="major",
                    message=f"{name} missing abilities in metadata",
                    details={"missing": missing, "parsed": titles},
                )
            )

    return findings


def import_campaign(
    pdf_path: Path,
    *,
    campaign_id: str,
    campaign_title: str,
) -> str:
    result = import_pdf(
        pdf_path,
        campaign_id=campaign_id,
        campaign_title=campaign_title,
        game_system="cof2",
    )
    if result.status != "completed":
        raise RuntimeError(
            f"Import failed for {pdf_path.name}: {result.status} — {result.error_message}"
        )
    assert result.document_id is not None
    return result.document_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--momie-pdf", type=Path, default=DEFAULT_MOMIE_PDF)
    parser.add_argument("--faelys-pdf", type=Path, default=DEFAULT_FAELYS_PDF)
    parser.add_argument("--skip-import", action="store_true")
    parser.add_argument("--momie-document-id", default="")
    parser.add_argument("--faelys-document-id", default="")
    args = parser.parse_args()

    findings: list[Finding] = []
    document_ids: dict[str, str] = {}

    if not args.skip_import:
        momie_pdf = resolve_pdf(args.momie_pdf, glob_pattern="*Mondanites*.pdf")
        faelys_pdf = resolve_pdf(args.faelys_pdf, glob_pattern="*Faelys*.pdf")
        print(f"Importing momie from {momie_pdf}")
        document_ids["momie"] = import_campaign(
            momie_pdf,
            campaign_id="momie",
            campaign_title="Mondanités et Momie",
        )
        print(f"Importing faelys from {faelys_pdf}")
        document_ids["faelys"] = import_campaign(
            faelys_pdf,
            campaign_id="dernier-faelys",
            campaign_title="Le Dernier Faelys",
        )
    else:
        if not args.momie_document_id or not args.faelys_document_id:
            parser.error("--skip-import requires --momie-document-id and --faelys-document-id")
        document_ids["momie"] = args.momie_document_id
        document_ids["faelys"] = args.faelys_document_id

    with get_connection() as conn:
        repo = RawRepository(conn)
        findings.extend(audit_momie(repo, document_ids["momie"]))
        findings.extend(audit_faelys(repo, document_ids["faelys"]))

    report = {
        "document_ids": document_ids,
        "finding_count": len(findings),
        "findings": [asdict(finding) for finding in findings],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if findings:
        print(f"\n{len(findings)} audit issue(s) remain.", file=sys.stderr)
        return 1
    print("\nAll audit checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
