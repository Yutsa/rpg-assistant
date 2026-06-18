"""COF2 regressions for Mortelle Xélys, Croissez et multipliez, Retour en grâce."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from rpg_ingest.raw.block_merging import merge_fragmented_blocks
from rpg_ingest.raw.filtering import filter_watermark_blocks
from rpg_ingest.raw.layout import extract_layout_pages
from rpg_ingest.raw.stat_blocks import resolve_profile
from tests.fixtures.pipeline import PipelineResult, run_raw_extraction_pipeline

PDF_DIR = Path("data/pdfs")
XELYS = PDF_DIR / "COF2_Mortelle_Xelys.pdf"
CROISSEZ = PDF_DIR / "COF2_Croissez_Et_Multipliez.pdf"
RETOUR = PDF_DIR / "COF2_Retour_En_Grace.pdf"


def _pipeline(pdf: Path) -> PipelineResult:
    document = pymupdf.open(pdf)
    pages = extract_layout_pages(document)
    return run_raw_extraction_pipeline(
        pages,
        campaign_id="audit-test",
        document_id="doc_audit_test",
        game_system="cof2",
    )


@pytest.mark.skipif(not XELYS.is_file(), reason="COF2 Mortelle Xélys PDF not available")
def test_xelys_no_table_row_sections() -> None:
    result = _pipeline(XELYS)
    titles = {section.title for section in result.sections}
    assert "J-15" not in titles
    assert "J-12" not in titles


@pytest.mark.skipif(not XELYS.is_file(), reason="COF2 Mortelle Xélys PDF not available")
def test_xelys_surveillance_text_in_section() -> None:
    result = _pipeline(XELYS)
    chunks = result.chunks
    surveillance_chunks = [
        chunk
        for chunk in chunks
        if "Pseck et Hermésia guettent" in chunk.text
    ]
    assert surveillance_chunks
    section = next(s for s in result.sections if s.id == surveillance_chunks[0].section_id)
    assert section.title == "SURVEILLANCE"


@pytest.mark.skipif(not CROISSEZ.is_file(), reason="COF2 Croissez PDF not available")
def test_croissez_panthere_abilities() -> None:
    result = _pipeline(CROISSEZ)
    panthere = next(
        chunk
        for chunk in result.chunks
        if chunk.chunk_type_hint == "stat_block"
        and (chunk.metadata.get("stat_block") or {}).get("name") == "PANTHÈRE"
    )
    titles = {ability["title"] for ability in panthere.metadata["stat_block"]["abilities"]}
    assert "EMBUSCADE" in titles
    assert "DÉVORER" in titles


@pytest.mark.skipif(not RETOUR.is_file(), reason="COF2 Retour en grâce PDF not available")
def test_retour_demasquer_chunk_not_truncated() -> None:
    result = _pipeline(RETOUR)
    section = next(s for s in result.sections if s.title == "Démasquer l’espion")
    chunks = [chunk for chunk in result.chunks if chunk.section_id == section.id]
    assert chunks
    text = chunks[0].text
    assert "PJ obtiennent un indice" in text
    assert not text.rstrip().endswith("Les")


@pytest.mark.skipif(not RETOUR.is_file(), reason="COF2 Retour en grâce PDF not available")
def test_retour_organiser_reception_title_merged() -> None:
    result = _pipeline(RETOUR)
    titles = {section.title for section in result.sections}
    assert "Organiser une réception" in titles
    assert "réception" not in titles


@pytest.mark.skipif(not RETOUR.is_file(), reason="COF2 Retour en grâce PDF not available")
def test_retour_page10_wrap_merge() -> None:
    document = pymupdf.open(RETOUR)
    pages = extract_layout_pages(document)
    profile = resolve_profile("cof2", pages)
    pages = filter_watermark_blocks(pages).pages
    merged = merge_fragmented_blocks(pages, profile=profile).pages
    page = next(item for item in merged if item.page_number == 10)
    demasquer_blocks = [block for block in page.blocks if "PJ obtiennent" in block.text]
    assert len(demasquer_blocks) == 1


@pytest.mark.skipif(not XELYS.is_file(), reason="COF2 Mortelle Xélys PDF not available")
def test_xelys_stat_block_names_strip_drm() -> None:
    result = _pipeline(XELYS)
    names = {
        (chunk.metadata.get("stat_block") or {}).get("name")
        for chunk in result.chunks
        if chunk.chunk_type_hint == "stat_block"
    }
    names.discard(None)
    names.discard("")
    assert "HERMÉSIA" in names
    assert all("\x03" not in (name or "") for name in names)


@pytest.mark.skipif(not XELYS.is_file(), reason="COF2 Mortelle Xélys PDF not available")
def test_xelys_sables_nested_under_pistes() -> None:
    result = _pipeline(XELYS)
    pistes = next(s for s in result.sections if s.title == "LES PISTES À SUIVRE")
    sables = next(
        s for s in result.sections if s.title.replace("\n", " ") == "Les mercenaires Sables rouges"
    )
    assert sables.parent_section_id == pistes.id
    sables_chunks = [c for c in result.chunks if c.section_id == sables.id]
    assert sables_chunks
    assert "Abel" in sables_chunks[0].text


@pytest.mark.skipif(not RETOUR.is_file(), reason="COF2 Retour en grâce PDF not available")
def test_retour_passage_secret_chunk_assigned() -> None:
    result = _pipeline(RETOUR)
    section = next(s for s in result.sections if s.title == "Un passage secret")
    chunks = [c for c in result.chunks if c.section_id == section.id]
    assert chunks
    assert "tour sud-ouest" in chunks[0].text.lower()


@pytest.mark.skipif(not RETOUR.is_file(), reason="COF2 Retour en grâce PDF not available")
def test_retour_recompense_p16_chunk_assigned() -> None:
    result = _pipeline(RETOUR)
    section = next(
        s for s in result.sections if s.title == "RÉCOMPENSE EN POINTS DE FAVEUR" and s.page_start == 16
    )
    chunks = [c for c in result.chunks if c.section_id == section.id]
    assert chunks
    assert "Démasquer les hommes de main" in chunks[0].text


@pytest.mark.skipif(not RETOUR.is_file(), reason="COF2 Retour en grâce PDF not available")
def test_retour_no_genealogy_manthine_section() -> None:
    result = _pipeline(RETOUR)
    assert not any(s.title == "Manthine" for s in result.sections)
