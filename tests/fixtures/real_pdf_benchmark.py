"""Static expectations and runners for real COF2 PDF ingestion benchmarks.

PDFs are never committed. Resolve paths via environment variables (see
``.env.example``) or optional local fallback paths.

Expectations are derived from:
- ``docs/audits/comparaison-pdf-ingestion-cof2/RAPPORT.md``
- ``tests/test_mondanites_chunking.py`` (regression suite)
- ``tests/fixtures/cof2_audit_expectations.py``
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from rpg_ingest.raw.providers.legacy import LegacyExtractionProvider
from rpg_core.models.raw import ChunkRecord, SectionRecord
from tests.fixtures.cof2_audit_expectations import (
    CENTAURE_ABILITIES,
    FEE_ABILITIES,
    FAELYS_BACKSTORY_MARKERS,
    FAELYS_CREDITS_MARKERS,
    FAELYS_CREDITS_SECTION,
    FAELYS_IMPLICATION_SECTION,
    FAELYS_INTRO_MARKERS,
    FAELYS_INTRO_SECTION,
    FAELYS_SHADOW_BOX_TITLE,
    FAELYS_ZONE_TITLES,
    MOMIE_CREDITS_MARKERS,
    MOMIE_SYNOPSIS_MARKERS,
    MOMIE_SYNOPSIS_SECTION,
    SOMBRE_FEE_ABILITIES,
)
from tests.fixtures.pipeline import (
    chunk_texts_for_section,
    section_by_title,
    stat_block_ability_titles,
)
from tests.fixtures.provider_benchmark import run_legacy_pipeline


def _normalize_text(value: str) -> str:
    text = value.replace("\u2019", "'").replace("\u2018", "'")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    normalized = _normalize_text(text)
    return any(_normalize_text(marker) in normalized for marker in markers)


def _find_section(
    sections: list[SectionRecord],
    title_substr: str,
) -> SectionRecord | None:
    needle = _normalize_text(title_substr)
    for section in sections:
        if needle in _normalize_text(section.title):
            return section
    return None


def _find_partie_section(
    sections: list[SectionRecord],
    roman: str,
) -> SectionRecord:
    """Match PARTIE I/II/III/IV without confusing PARTIE I with PARTIE II."""
    pattern = re.compile(rf"partie\s+{roman}\b", re.IGNORECASE)
    matches = [
        section
        for section in sections
        if pattern.search(_normalize_text(section.title))
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return matches[0]
    raise AssertionError(
        f"Section not found for PARTIE {roman}; got {[s.title for s in sections]}"
    )


def _chunk_page_numbers(chunks: list[ChunkRecord]) -> set[int]:
    pages: set[int] = set()
    for chunk in chunks:
        pages.update(range(chunk.page_start, chunk.page_end + 1))
        for span in chunk.source_spans:
            pages.add(span.page)
    return pages


def _ability_titles_match(actual: list[str], expected: tuple[str, ...]) -> bool:
    if len(actual) != len(expected):
        return False
    for got, want in zip(actual, expected, strict=True):
        if got == want:
            continue
        if "ARAIGN" in want and "ARAIGN" in got:
            continue
        return False
    return True


def _chunks_on_page(chunks: list[ChunkRecord], page: int) -> list[ChunkRecord]:
    return [chunk for chunk in chunks if chunk.page_start <= page <= chunk.page_end]


def _chunk_text_on_page(chunks: list[ChunkRecord], page: int) -> str:
    return "\n".join(chunk.text for chunk in _chunks_on_page(chunks, page))


def _section_text(chunks: list[ChunkRecord], section_id: str) -> str:
    return "\n".join(chunk.text for chunk in chunks if chunk.section_id == section_id)


@dataclass(frozen=True)
class RealPdfSpec:
    """Descriptor for a proprietary benchmark PDF living outside the repo."""

    benchmark_id: str
    env_var: str
    filename: str
    campaign_id: str
    fallback_paths: tuple[str, ...] = ()
    game_system: str = "cof2"
    page_count: int = 20


@dataclass
class BenchmarkRun:
    benchmark_id: str
    pdf_path: Path
    sections: list[SectionRecord]
    chunks: list[ChunkRecord]
    blocks: int
    missing_blocks: int
    duplicate_chunks: int


@dataclass
class BenchmarkCheck:
    """Named assertion with audit traceability."""

    check_id: str
    pages: str
    description: str
    fn: Callable[[BenchmarkRun], None]


def resolve_real_pdf_path(spec: RealPdfSpec) -> Path | None:
    """Resolve a benchmark PDF from env var then optional fallback paths."""
    candidates: list[Path] = []
    env_value = os.environ.get(spec.env_var, "").strip()
    if env_value:
        candidates.append(Path(env_value).expanduser())
    for fallback in spec.fallback_paths:
        candidates.append(Path(fallback).expanduser())
    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None


def skip_reason(spec: RealPdfSpec) -> str:
    env_hint = f"set {spec.env_var}=/path/to/{spec.filename}"
    fallback_hint = (
        f" or place the file at one of: {', '.join(spec.fallback_paths)}"
        if spec.fallback_paths
        else ""
    )
    return f"{spec.filename} not available ({env_hint}{fallback_hint})"


def run_real_pdf_benchmark(
    spec: RealPdfSpec,
    pdf_path: Path,
    *,
    document_id: str | None = None,
) -> BenchmarkRun:
    doc_id = document_id or f"bench_{spec.benchmark_id}_legacy"
    extraction = LegacyExtractionProvider().extract(pdf_path)
    score, chunks, sections = run_legacy_pipeline(
        extraction.pages,
        campaign_id=spec.campaign_id,
        document_id=doc_id,
        game_system=spec.game_system,
    )
    return BenchmarkRun(
        benchmark_id=spec.benchmark_id,
        pdf_path=pdf_path,
        sections=sections,
        chunks=chunks,
        blocks=score.blocks,
        missing_blocks=score.missing_blocks,
        duplicate_chunks=score.duplicate_chunks,
    )


def run_benchmark_checks(run: BenchmarkRun, checks: tuple[BenchmarkCheck, ...]) -> None:
    for check in checks:
        check.fn(run)


MONDANITES_SPEC = RealPdfSpec(
    benchmark_id="mondanites",
    env_var="RPG_PDF_MOMIE",
    filename="COF2_10_Mondanites_Et_Momies_web_v1a.pdf",
    campaign_id="momie",
    fallback_paths=(
        "/workspace/data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf",
        "/home/edouard/Téléchargements/COF2_10_Mondanites_Et_Momies_web_v1a.pdf",
        "~/Downloads/COF2_10_Mondanites_Et_Momies_web_v1a.pdf",
    ),
)

FAELYS_SPEC = RealPdfSpec(
    benchmark_id="faelys",
    env_var="RPG_PDF_FAELYS",
    filename="COF2_07_Le_Dernier_Faelys_web_v0.pdf",
    campaign_id="dernier-faelys",
    fallback_paths=(
        "/workspace/data/pdfs/COF2_07_Le_Dernier_Faelys_web_v0.pdf",
        "/home/edouard/Téléchargements/COF2_07_Le_Dernier_Faelys_web_v0.pdf",
        "~/Downloads/COF2_07_Le_Dernier_Faelys_web_v0.pdf",
    ),
)

REAL_PDF_SPECS: tuple[RealPdfSpec, ...] = (MONDANITES_SPEC, FAELYS_SPEC)


def _mondanites_global_quality(run: BenchmarkRun) -> None:
    assert run.missing_blocks == 0, "content blocks must be covered exactly once"
    assert run.duplicate_chunks == 0, "no duplicate chunk signatures"
    assert len(run.chunks) <= 80, f"too many chunks ({len(run.chunks)})"
    assert all(len(section.title.strip()) != 1 for section in run.sections)
    titles = [section.title for section in run.sections]
    assert not any("AZULRIA" in title for title in titles)
    assert not any("TALESS RHANN" in title for title in titles)


def _mondanites_page5_intro_sections(run: BenchmarkRun) -> None:
    intro_titles = [
        section.title
        for section in run.sections
        if section.page_start <= 7 and section.page_end >= 5
    ]
    assert not any(title == "ET MOMIE" for title in intro_titles)
    assert not any(title == "MONDANITÉS" for title in intro_titles)

    en_quelques = section_by_title(run.sections, "EN QUELQUES MOTS")
    partie = _find_partie_section(run.sections, "i")
    assert en_quelques.parent_section_id is None
    assert en_quelques.parent_section_id != partie.id


def _mondanites_page5_en_quelques_mots_chunk(run: BenchmarkRun) -> None:
    texts = chunk_texts_for_section(run.chunks, run.sections, "EN QUELQUES MOTS")
    assert len(texts) == 1
    assert "Pendant une soirée" in texts[0]
    assert "vestiges d'un temple" not in texts[0]


def _mondanites_page5_7_grandes_lignes(run: BenchmarkRun) -> None:
    partie = _find_partie_section(run.sections, "i")
    grandes_lignes = section_by_title(run.sections, "Les grandes lignes")
    histoire_mj = section_by_title(run.sections, "histoire pour le MJ")
    assert grandes_lignes.parent_section_id == partie.id
    assert histoire_mj.parent_section_id == partie.id
    lgl_text = _section_text(run.chunks, grandes_lignes.id)
    assert "vestiges" in lgl_text and "abattoirs" in lgl_text
    assert "Depuis lors" not in lgl_text


def _mondanites_page7_8_histoire_mj(run: BenchmarkRun) -> None:
    histoire_mj = section_by_title(run.sections, "histoire pour le MJ")
    mj_text = _section_text(run.chunks, histoire_mj.id)
    assert "Taless Rhann" in mj_text
    assert "La tombe resta inviolée" in mj_text
    assert "Depuis lors" in mj_text
    assert mj_text.index("Taless Rhann") < mj_text.index("La tombe resta")
    assert mj_text.index("La tombe resta") < mj_text.index("Depuis lors")
    page8_text = _chunk_text_on_page(
        [c for c in run.chunks if c.section_id == histoire_mj.id],
        8,
    )
    if page8_text:
        assert "Il est temps pour les PJ" in page8_text or "temps pour les PJ" in mj_text


def _mondanites_page8_no_false_introduction(run: BenchmarkRun) -> None:
    false_intro = [
        section
        for section in run.sections
        if section.title == "Introduction" and section.page_start == 8
    ]
    assert not false_intro
    intro_page8_chunks = [
        chunk
        for chunk in run.chunks
        if chunk.page_start <= 8 <= chunk.page_end
        and any(
            section.title == "Introduction" and section.id == chunk.section_id
            for section in run.sections
        )
    ]
    assert not intro_page8_chunks


def _mondanites_page8_acteurs(run: BenchmarkRun) -> None:
    acteurs = section_by_title(run.sections, "différents acteurs")
    acteurs_text = _section_text(run.chunks, acteurs.id)
    for name in ("Kalian", "Debranne", "Azulria"):
        assert name in acteurs_text, f"actor {name!r} missing from acteurs section"


def _mondanites_page15_stat_blocks(run: BenchmarkRun) -> None:
    page_15_stats = [
        chunk
        for chunk in run.chunks
        if chunk.page_start <= 15 <= chunk.page_end and chunk.chunk_type_hint == "stat_block"
    ]
    assert page_15_stats
    names = [
        (chunk.metadata.get("stat_block") or {}).get("name", "")
        for chunk in page_15_stats
    ]
    joined = " ".join(names).upper()
    assert "AZULRIA" in joined or any(
        "AZULRIA" in chunk.text.upper() for chunk in page_15_stats
    )
    assert "TALESS" in joined or any(
        "TALESS" in chunk.text.upper() for chunk in page_15_stats
    )


def _mondanites_partie_ii_drame(run: BenchmarkRun) -> None:
    drame = section_by_title(run.sections, "cabinet de curiosit")
    partie_ii = _find_partie_section(run.sections, "ii")
    drame_text = _section_text(run.chunks, drame.id)
    partie_ii_text = _section_text(run.chunks, partie_ii.id)
    assert "La salle mesure" in drame_text
    assert "La salle mesure" not in partie_ii_text
    assert "Le manoir Horsbi" in drame_text
    assert "état de conservation exceptionnel" in drame_text

    investigations = section_by_title(run.sections, "investigations imm")
    inv_text = _section_text(run.chunks, investigations.id)
    assert "état de conservation exceptionnel" not in inv_text
    assert "Une fois le sable retombé" in inv_text


def _momie_synopsis_not_mixed_with_credits(run: BenchmarkRun) -> None:
    synopsis_text = "\n".join(
        chunk_texts_for_section(run.chunks, run.sections, MOMIE_SYNOPSIS_SECTION)
    )
    assert synopsis_text, f"section {MOMIE_SYNOPSIS_SECTION!r} expected"
    assert _contains_any(synopsis_text, MOMIE_SYNOPSIS_MARKERS)
    assert not _contains_any(synopsis_text, MOMIE_CREDITS_MARKERS)
    for chunk in run.chunks:
        if chunk.page_start <= 2 <= chunk.page_end and chunk.page_end >= 4:
            assert not (
                _contains_any(chunk.text, MOMIE_SYNOPSIS_MARKERS)
                and _contains_any(chunk.text, MOMIE_CREDITS_MARKERS)
            )


def _mondanites_page5_no_content_scramble(run: BenchmarkRun) -> None:
    """Page 5 body sections must not cross-contaminate."""
    en_quelques = _find_section(run.sections, "EN QUELQUES MOTS")
    assert en_quelques is not None, "EN QUELQUES MOTS section expected on page 5"
    eq_chunks = [c for c in run.chunks if c.section_id == en_quelques.id]
    assert eq_chunks, "EN QUELQUES MOTS must have at least one chunk"
    eq_text = "\n".join(c.text for c in eq_chunks)
    assert "Pendant une soirée" in eq_text, "synopsis box text must stay in EN QUELQUES MOTS"

    fiche = _find_section(run.sections, "FICHE TECHNIQUE")
    if fiche is not None:
        fiche_text = _section_text(run.chunks, fiche.id)
        assert "Taless Rhann" not in fiche_text, "MJ backstory must not leak into FICHE TECHNIQUE"
        assert "Les grandes lignes" not in fiche_text, "section body must not start inside FICHE TECHNIQUE"


def _mondanites_no_spurious_stat_titles(run: BenchmarkRun) -> None:
    """Watermark/stat-block debris must not become section headings (p.15)."""
    for section in run.sections:
        title = _normalize_text(section.title)
        assert "taless rhann" not in title or "histoire" in title, (
            f"spurious stat/watermark section title: {section.title!r}"
        )
        assert not title.startswith("w w w"), f"watermark debris as section: {section.title!r}"


def _faelys_global_quality(run: BenchmarkRun) -> None:
    assert run.missing_blocks == 0
    assert run.duplicate_chunks == 0
    assert len(run.sections) >= 30, "expected rich section tree on 20-page scenario"


def _faelys_audit2_credits_vs_intro(run: BenchmarkRun) -> None:
    credits_text = "\n".join(
        chunk_texts_for_section(run.chunks, run.sections, FAELYS_CREDITS_SECTION)
    )
    assert credits_text, "CRÉDITS section expected"
    assert _contains_any(credits_text, FAELYS_CREDITS_MARKERS)
    assert not _contains_any(credits_text, FAELYS_INTRO_MARKERS)
    assert not _contains_any(credits_text, FAELYS_BACKSTORY_MARKERS)

    intro_text = "\n".join(
        chunk_texts_for_section(run.chunks, run.sections, FAELYS_INTRO_SECTION)
    )
    assert intro_text, "EN QUELQUES MOTS section expected"
    assert _contains_any(intro_text, FAELYS_INTRO_MARKERS)
    assert not _contains_any(intro_text, FAELYS_CREDITS_MARKERS)

    narrative_markers = FAELYS_INTRO_MARKERS + FAELYS_BACKSTORY_MARKERS
    for chunk in run.chunks:
        assert not (
            _contains_any(chunk.text, FAELYS_CREDITS_MARKERS)
            and _contains_any(chunk.text, narrative_markers)
        ), f"chunk mixes credits and narrative (p.{chunk.page_start})"


def _faelys_backstory_separate(run: BenchmarkRun) -> None:
    """Backstory paragraph (Le bois d'Astréis) must not live in CRÉDITS."""
    credits_text = "\n".join(
        chunk_texts_for_section(run.chunks, run.sections, FAELYS_CREDITS_SECTION)
    )
    assert not _contains_any(credits_text, FAELYS_BACKSTORY_MARKERS)

    backstory_chunks = [
        chunk
        for chunk in run.chunks
        if _contains_any(chunk.text, FAELYS_BACKSTORY_MARKERS)
    ]
    assert backstory_chunks, "expected backstory paragraph somewhere in document"
    for chunk in backstory_chunks:
        section = next(s for s in run.sections if s.id == chunk.section_id)
        assert section.title != FAELYS_CREDITS_SECTION, (
            "backstory must not be stored under CRÉDITS"
        )


def _faelys_audit3_shadow_box_title(run: BenchmarkRun) -> None:
    titles = [_normalize_text(section.title) for section in run.sections]
    truncated = _normalize_text("LES FELIS ET LE PLAN DE")
    split_tail = _normalize_text("L'OMBRE FEERIQUE")
    full = _normalize_text(FAELYS_SHADOW_BOX_TITLE)
    assert not any(title == truncated for title in titles)
    assert not (
        any(split_tail in title for title in titles)
        and not any(full in title for title in titles)
    ), "shadow-box title split across sections"
    assert any(
        full in title or ("felis" in title and "ombre" in title) for title in titles
    ), "expected unified shadow-box section title on page 7"


def _faelys_audit4_zone_hierarchy(run: BenchmarkRun) -> None:
    implication = _find_section(run.sections, FAELYS_IMPLICATION_SECTION)
    assert implication is not None
    for zone_title in FAELYS_ZONE_TITLES:
        zone = _find_section(run.sections, zone_title)
        assert zone is not None, f"missing zone section {zone_title!r}"
        assert zone.parent_section_id != implication.id, (
            f"{zone.title!r} must not be child of IMPLICATION DES PJ (p.{zone.page_start})"
        )


def _faelys_audit8_palace_page_bridge(run: BenchmarkRun) -> None:
    palace = _find_section(run.sections, "palais des fleurs")
    assert palace is not None
    palace_chunks = [c for c in run.chunks if c.section_id == palace.id]
    assert palace_chunks
    palace_text = "\n".join(c.text for c in palace_chunks)
    page_numbers = _chunk_page_numbers(palace_chunks)
    assert 10 in page_numbers, "palace section should cover page 10"
    assert 11 in page_numbers, "palace section must include page 11 (no 10→12 jump)"
    assert _contains_any(palace_text, ("énigme", "exprime", "entrevue", "reine"))


def _faelys_audit9_mille_pattes(run: BenchmarkRun) -> None:
    page12_stats = [
        c
        for c in run.chunks
        if c.page_start <= 12 <= c.page_end and c.chunk_type_hint == "stat_block"
    ]
    mille = next(
        (c for c in page12_stats if "MILLE-PATTES" in c.text.upper()),
        None,
    )
    assert mille is not None, "MILLE-PATTES stat chunk expected on page 12"
    assert "difficulté" in mille.text.casefold()
    assert "12 pour" in mille.text or "1/2 DM" in mille.text.upper() or "½ DM" in mille.text
    orphans = [
        c
        for c in run.chunks
        if c.page_start == 12
        and c.chunk_type_hint != "stat_block"
        and "12 pour" in c.text
    ]
    assert not orphans, "poison DC fragment must not be a separate lore chunk"


def _faelys_audit10_centaures_section(run: BenchmarkRun) -> None:
    centaures = _find_section(run.sections, "Les centaures")
    champs = _find_section(run.sections, "champs repoussés")
    assert centaures is not None
    assert champs is not None
    centaures_text = _section_text(run.chunks, centaures.id)
    champs_text = _section_text(run.chunks, champs.id)
    assert _contains_any(centaures_text, ("centaure", "homade", "CENTAURE"))
    if _contains_any(centaures_text, ("s'allier", "combattre", "humanoides")):
        assert not _contains_any(champs_text, ("s'allier", "combattre"))
    page16_centaures = _chunk_text_on_page(
        [c for c in run.chunks if c.section_id == centaures.id],
        16,
    )
    if page16_centaures:
        assert "centaure" in _normalize_text(page16_centaures)


def _faelys_audit5_6_7_stat_abilities(run: BenchmarkRun) -> None:
    fee_titles = stat_block_ability_titles(run.chunks, "FÉE")
    if fee_titles:
        assert _ability_titles_match(fee_titles, FEE_ABILITIES), (
            f"FÉE abilities: got {fee_titles}"
        )

    centaure_titles = stat_block_ability_titles(run.chunks, "CENTAURE")
    if centaure_titles:
        assert _ability_titles_match(centaure_titles, CENTAURE_ABILITIES), (
            f"CENTAURE abilities: got {centaure_titles}"
        )

    sombre_titles = stat_block_ability_titles(run.chunks, "SOMBRE FÉE")
    if not sombre_titles:
        sombre_titles = stat_block_ability_titles(run.chunks, "ARACHNO")
    if sombre_titles:
        assert _ability_titles_match(sombre_titles, SOMBRE_FEE_ABILITIES), (
            f"SOMBRE FÉE abilities: got {sombre_titles}"
        )


def _faelys_prairie_section(run: BenchmarkRun) -> None:
    """Zone section for page 12 must exist with carnivorous plant encounter."""
    prairie = _find_section(run.sections, "prairie fleurie")
    assert prairie is not None, "La prairie fleurie section expected"
    prairie_text = _section_text(run.chunks, prairie.id)
    assert _contains_any(prairie_text, ("plante", "carnivore", "herbe"))
    page12 = _chunk_text_on_page(
        [c for c in run.chunks if c.section_id == prairie.id],
        12,
    )
    assert page12, "prairie fleurie must have content on page 12"


def _faelys_no_sentence_fragment_sections(run: BenchmarkRun) -> None:
    """Column body text must not become section titles (p.12 regression)."""
    fragment_markers = (
        "s'exprime d'une voix",
        "énonce",
        "l'énigme",
    )
    for section in run.sections:
        title = _normalize_text(section.title)
        if any(_normalize_text(marker) in title for marker in fragment_markers):
            raise AssertionError(
                f"sentence fragment used as section title: {section.title!r}"
            )


MONDANITES_CHECKS: tuple[BenchmarkCheck, ...] = (
    BenchmarkCheck("global", "all", "coverage and chunk budget", _mondanites_global_quality),
    BenchmarkCheck("intro-sections", "5-7", "intro headings not spread titles", _mondanites_page5_intro_sections),
    BenchmarkCheck("en-quelques-mots", "5", "synopsis box chunk", _mondanites_page5_en_quelques_mots_chunk),
    BenchmarkCheck("page5-scramble", "5", "no cross-section contamination on p5", _mondanites_page5_no_content_scramble),
    BenchmarkCheck("grandes-lignes", "5-7", "part I body vs MJ epilogue", _mondanites_page5_7_grandes_lignes),
    BenchmarkCheck("histoire-mj", "7-8", "MJ narrative order and p8 wrap", _mondanites_page7_8_histoire_mj),
    BenchmarkCheck("no-false-intro", "8", "no Introduction on page 8", _mondanites_page8_no_false_introduction),
    BenchmarkCheck("acteurs", "8", "complete actor list", _mondanites_page8_acteurs),
    BenchmarkCheck("stat-blocks", "15", "AZULRIA and TALESS stat blocks", _mondanites_page15_stat_blocks),
    BenchmarkCheck("no-spurious-titles", "15", "no watermark/stat debris as sections", _mondanites_no_spurious_stat_titles),
    BenchmarkCheck("partie-ii-drame", "17+", "cabinet vs investigations split", _mondanites_partie_ii_drame),
    BenchmarkCheck(
        "synopsis-credits",
        "2,4",
        "synopsis must not include BBE credits (audit #1)",
        _momie_synopsis_not_mixed_with_credits,
    ),
)

FAELYS_CHECKS: tuple[BenchmarkCheck, ...] = (
    BenchmarkCheck("global", "all", "coverage and section richness", _faelys_global_quality),
    BenchmarkCheck("credits-intro", "4-5", "credits vs EN QUELQUES MOTS", _faelys_audit2_credits_vs_intro),
    BenchmarkCheck("backstory-split", "5", "Astréis backstory not in CRÉDITS", _faelys_backstory_separate),
    BenchmarkCheck("shadow-box", "7", "unified encadré title", _faelys_audit3_shadow_box_title),
    BenchmarkCheck("zone-hierarchy", "12-19", "zones not under IMPLICATION", _faelys_audit4_zone_hierarchy),
    BenchmarkCheck("palace-bridge", "10-12", "page 11 inside palace section", _faelys_audit8_palace_page_bridge),
    BenchmarkCheck("prairie-section", "12", "La prairie fleurie zone section", _faelys_prairie_section),
    BenchmarkCheck("no-fragment-titles", "12", "no sentence fragments as section titles", _faelys_no_sentence_fragment_sections),
    BenchmarkCheck("mille-pattes", "12", "complete MILLE-PATTES stat block", _faelys_audit9_mille_pattes),
    BenchmarkCheck("centaures-column", "16", "centaurs text in centaures section", _faelys_audit10_centaures_section),
    BenchmarkCheck("stat-abilities", "15-19", "FÉE/CENTAURE/SOMBRE FÉE abilities", _faelys_audit5_6_7_stat_abilities),
)

BENCHMARK_CHECKS: dict[str, tuple[BenchmarkCheck, ...]] = {
    "mondanites": MONDANITES_CHECKS,
    "faelys": FAELYS_CHECKS,
}

