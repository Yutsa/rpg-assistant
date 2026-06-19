"""Benchmark helpers comparing legacy vs pymupdf4llm extraction pipelines."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rpg_core.models.raw import ChunkRecord, SectionRecord
from tests.fixtures.pipeline import PipelineResult, run_raw_extraction_pipeline_pdf


@dataclass
class ExtractorScore:
    name: str
    section_titles: list[str] = field(default_factory=list)
    chunk_count: int = 0
    empty_section_count: int = 0
    duplicate_chunk_count: int = 0
    section_chunk_map: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    legacy: ExtractorScore
    modern: ExtractorScore
    legacy_wins: int = 0
    modern_wins: int = 0
    ties: int = 0
    details: list[str] = field(default_factory=list)


def _score_from_pipeline(name: str, result: PipelineResult) -> ExtractorScore:
    from rpg_ingest.raw.chunking import chunk_uniqueness_stats

    uniqueness = chunk_uniqueness_stats(result.chunks)
    section_by_id = {section.id: section for section in result.sections}
    section_chunk_map: dict[str, list[str]] = {}
    for chunk in result.chunks:
        section = section_by_id.get(chunk.section_id or "")
        title = section.title if section else "(none)"
        section_chunk_map.setdefault(title, []).append(chunk.text)

    return ExtractorScore(
        name=name,
        section_titles=[section.title for section in result.sections],
        chunk_count=len(result.chunks),
        empty_section_count=sum(
            1
            for section in result.sections
            if not any(chunk.section_id == section.id for chunk in result.chunks)
        ),
        duplicate_chunk_count=uniqueness["duplicate_chunk_count"],
        section_chunk_map=section_chunk_map,
    )


def compare_pipelines(
    pdf_path: Path,
    *,
    campaign_id: str = "bench",
    legacy_document_id: str = "doc_legacy",
    modern_document_id: str = "doc_modern",
) -> ComparisonResult:
    legacy_result = run_raw_extraction_pipeline_pdf(
        pdf_path,
        campaign_id=campaign_id,
        document_id=legacy_document_id,
        extractor="legacy",
    )
    modern_result = run_raw_extraction_pipeline_pdf(
        pdf_path,
        campaign_id=campaign_id,
        document_id=modern_document_id,
        extractor="pymupdf4llm",
    )
    legacy = _score_from_pipeline("legacy", legacy_result)
    modern = _score_from_pipeline("pymupdf4llm", modern_result)

    details: list[str] = []
    legacy_wins = 0
    modern_wins = 0
    ties = 0

    for metric, better in (
        ("duplicate_chunk_count", "lower"),
        ("empty_section_count", "lower"),
    ):
        left = getattr(legacy, metric)
        right = getattr(modern, metric)
        if left == right:
            ties += 1
            details.append(f"{metric}: tie ({left})")
        elif (better == "lower" and right < left) or (better == "higher" and right > left):
            modern_wins += 1
            details.append(f"{metric}: pymupdf4llm better ({right} vs {left})")
        else:
            legacy_wins += 1
            details.append(f"{metric}: legacy better ({left} vs {right})")

    legacy_titles = set(legacy.section_chunk_map)
    modern_titles = set(modern.section_chunk_map)
    if modern_titles >= legacy_titles:
        modern_wins += 1
        details.append("section titles: pymupdf4llm covers legacy titles")
    elif legacy_titles >= modern_titles:
        legacy_wins += 1
        details.append("section titles: legacy covers more")
    else:
        ties += 1
        details.append(
            f"section titles: partial overlap legacy-only={legacy_titles - modern_titles} "
            f"modern-only={modern_titles - legacy_titles}"
        )

    matching_sections = legacy_titles & modern_titles
    assignment_matches = 0
    assignment_total = 0
    for title in sorted(matching_sections):
        assignment_total += 1
        legacy_text = "\n\n".join(legacy.section_chunk_map.get(title, []))
        modern_text = "\n\n".join(modern.section_chunk_map.get(title, []))
        if legacy_text == modern_text:
            assignment_matches += 1
        else:
            details.append(
                f"chunk text differs for {title!r}: "
                f"legacy={legacy_text[:60]!r} modern={modern_text[:60]!r}"
            )
    if assignment_total and assignment_matches == assignment_total:
        modern_wins += 1
        details.append("chunk assignment: exact match on shared sections")
    elif assignment_matches > assignment_total // 2:
        ties += 1
        details.append(
            f"chunk assignment: partial match {assignment_matches}/{assignment_total}"
        )
    else:
        legacy_wins += 1
        details.append(
            f"chunk assignment: legacy closer {assignment_matches}/{assignment_total}"
        )

    return ComparisonResult(
        legacy=legacy,
        modern=modern,
        legacy_wins=legacy_wins,
        modern_wins=modern_wins,
        ties=ties,
        details=details,
    )


def modern_beats_legacy(comparison: ComparisonResult) -> bool:
    return comparison.modern_wins > comparison.legacy_wins


def modern_matches_or_beats_legacy(comparison: ComparisonResult) -> bool:
    return comparison.modern_wins >= comparison.legacy_wins
